-- Strict TLS for credentials and commands; never follows redirects or retries.
local Transport = {}
local BLOCK_TIMEOUT = 15
local TOTAL_TIMEOUT = 45
local ROOT = debug.getinfo(1, 'S').source:match('^@(.*/)') or 'plugins/weatherlockscreen.koplugin/'

function Transport.request(url, headers, body)
    if not url:match('^https://[a-z]+%.iot%.dreame%.tech:13267/') then return nil end
    local expected_host = url:match('^https://([^:]+):')
    local socketutil = require('socketutil')
    local socket = require('socket')
    local ssl = require('ssl')
    local http = require('socket.http')
    local ltn12 = require('ltn12')
    local chunks = {}; local bytes = 0; local started = os.time()
    local active
    local stage = 'network'
    local failure
    local response_started = false
    local function ioFailure(err, phase)
        if err == 'timeout' or err == 'wantread' or err == 'wantwrite' then return 'timeout_' .. phase end
        return phase
    end
    local function wifiState()
        local ok, on = pcall(function()return require('ui/network/manager'):isWifiOn() end)
        return ok and (on and 'on' or 'off') or 'unknown'
    end
    local wifi_before = wifiState()
    socketutil:set_timeout(BLOCK_TIMEOUT, TOTAL_TIMEOUT)
    local ok, status = pcall(function()
        local function create()
            local conn = {sock = assert(socket.tcp())}; active = conn
            function conn:settimeout()
                local remaining = TOTAL_TIMEOUT - (os.time() - started)
                if remaining <= 0 then failure = 'timeout_total'; error('Request deadline reached') end
                return self.sock:settimeout(math.min(BLOCK_TIMEOUT, remaining))
            end
            function conn:connect(host, port)
                assert(host == expected_host and tonumber(port) == 13267, 'Unexpected TLS endpoint')
                stage = 'tcp'
                local connected, err = self.sock:connect(host, port)
                if not connected then failure = ioFailure(err, 'tcp'); error('TCP connection failed') end
                stage = 'tls_setup'
                self.sock = assert(ssl.wrap(self.sock, {mode = 'client', protocol = 'any', verify = 'peer',
                    options = {'all', 'no_sslv2', 'no_sslv3', 'no_tlsv1', 'no_tlsv1_1'}, cafile = ROOT .. 'dreame-ca.pem'}))
                self.sock:sni(host); self:settimeout()
                stage = 'tls_handshake'
                local negotiated, err = self.sock:dohandshake()
                if not negotiated then failure = ioFailure(err, 'tls_handshake'); error('TLS handshake failed') end
                stage = 'tls_hostname'
                local cert = assert(self.sock:getpeercertificate())
                local verified, reason = require('dreame_tls').verify(cert, host)
                if not verified then stage = reason; error('TLS hostname verification failed') end
                stage = 'http'
                return 1
            end
            function conn:send( ... )
                stage = 'http_send'
                self:settimeout()
                local n, err, last = self.sock:send( ... )
                if not n then failure = ioFailure(err, 'http_send') end
                return n, err, last
            end
            function conn:receive( ... )
                stage = response_started and 'http_incomplete' or 'http_no_response'
                self:settimeout()
                local data, err, partial = self.sock:receive( ... )
                if (type(data) == 'string' and #data > 0)
                    or (type(partial) == 'string' and #partial > 0) then response_started = true end
                if err then failure = ioFailure(err, response_started and 'http_incomplete' or 'http_no_response') end
                return data, err, partial
            end
            function conn:getfd() return self.sock:getfd() end
            function conn:dirty() return self.sock:dirty() end
            function conn:close() return self.sock:close() end
            return conn
        end
        headers['content-length'] = tostring(#body)
        headers.connection = 'close'
        -- Use socket.http with our TLS socket so certificate hostname checks
        -- happen before any HTTP bytes (including tokens) are transmitted.
        local result, code = http.request{url = url, method = 'POST', headers = headers,
            source = ltn12.source.string(body), create = create, redirect = false,
            sink = function(chunk)
                if os.time() - started >= TOTAL_TIMEOUT then failure = 'timeout_total'; return nil, 'timeout' end
                if chunk then
                    bytes = bytes + #chunk; if bytes > 512 * 1024 then return nil, 'response too large' end
                    chunks[#chunks + 1] = chunk
                end
                return 1
            end}
        if not result then
            failure = failure or (type(code) == 'string' and code:lower():find('timeout', 1, true) and 'timeout' or stage)
        end
        return result and tonumber(code) or nil
    end)
    if active then pcall(active.close, active) end
    socketutil:reset_timeout()
    -- Do not return raw transport errors: libraries may include request details.
    pcall(function()
        local operation = url:find('/oauth/token', 1, true) and 'session'
            or (url:find('/sendCommand', 1, true) and 'robot' or 'cloud')
        require('logger').info('DreameTransport:', operation, 'phase=' .. stage,
            'result=' .. (ok and status and tostring(tonumber(status) or 0) or (failure or stage)),
            'elapsed=' .. tostring(os.time() - started),
            'wifi_before=' .. wifi_before, 'wifi_after=' .. wifiState())
    end)
    if not ok or not status then return nil, nil, failure or stage end
    return status, table.concat(chunks)
end

return Transport
