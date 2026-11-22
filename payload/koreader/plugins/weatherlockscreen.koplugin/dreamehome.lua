-- On-demand Dreamehome cloud client. No bridge, polling or MQTT service.
-- AGPL-3.0-or-later; protocol adapted from Tasshack/dreame-vacuum (MIT).
local Dreamehome = {}
local CID = 'EETjszu*XI5znHsI' -- Public app protocol constant, not a user credential.
local SALT = 'RAylYC%fmSKp7%Tq'
local AUTH = 'Basic ZHJlYW1lX2FwcHYxOkFQXmR2QHpAU1FZVnhOODg='
local regions = {eu = true, us = true, cn = true, sg = true, ru = true}
-- Community model identifiers for L50 Pro Ultra; hardware validation is pending.
local models = {['dreame.vacuum.r9445a'] = true, ['dreame.vacuum.r9445d'] = true,
    ['dreame.vacuum.r9445g'] = true}

function Dreamehome.supportedModel(model) return models[model] == true end

function Dreamehome.shortcutName(shortcut)
    local ok, name = pcall(require('mime').unb64, shortcut.name or '')
    if ok and type(name) == 'string' then return name:lower() end
end

function Dreamehome.discoveryMessage(devices)
    if #devices == 0 then
        return 'Signed in successfully, but this account has no visible robots in this region. Share the robot from the owner account, accept the invitation in Dreamehome, and confirm the account region.'
    end
    local identifiers, seen = {}, {}
    for _, d in ipairs(devices) do
        if Dreamehome.supportedModel(d.model) and (not d.did or not d.bindDomain) then
            return 'L50 Pro Ultra found, but its cloud routing information is missing. Check sharing permissions in Dreamehome.'
        end
        local model = type(d.model) == 'string' and #d.model <= 80
            and d.model:match('^[a-z0-9._%-]+$') and d.model or 'unknown identifier'
        if not seen[model] and #identifiers < 8 then identifiers[#identifiers + 1] = model; seen[model] = true end
    end
    return 'Signed in successfully. No supported L50 Pro Ultra identifier matched. Found: '
        .. table.concat(identifiers, ', ') .. '. Report these model identifiers; do not reset the robot.'
end

local function md5(s) return require('ffi/sha2').md5(s) end

local function json() return require('json') end

local function quote(s)
    return (s:gsub('([^%w%-._~])', function(c)return string.format('%%%02X', c:byte()) end))
end

local function decode(s)
    if type(s) ~= 'string' then return nil end
    local ok, v = pcall(json().decode, s)
    return ok and type(v) == 'table' and v or nil
end

local function connectionError(reason, context)
    local details = {tcp = 'Cannot reach the Dreame server (TCP/DNS). Check Wi-Fi and internet.',
        timeout = 'Dreame connection timed out.',
        timeout_tcp = 'Timed out connecting to the Dreame server (TCP).',
        timeout_tls_handshake = 'Timed out during the TLS handshake.',
        timeout_http_send = 'Timed out sending the request. Delivery is uncertain.',
        timeout_http_no_response = 'Timed out waiting for the first HTTP reply.',
        timeout_http_incomplete = 'Timed out receiving the rest of the HTTP reply.',
        timeout_total = 'The Dreame request exceeded its 45-second deadline.',
        tls_setup = 'TLS setup failed on this Kindle.',
        tls_handshake = 'TLS handshake failed. Check the Kindle date/time; TLS compatibility needs diagnosis.',
        tls_hostname = 'TLS certificate hostname verification failed. Connection was blocked.',
        tls_support = 'This Kindle TLS library exposes neither native hostname checking nor certificate DNS names. Connection was blocked.',
        http = 'Connection closed before a complete HTTP response.',
        http_send = 'Connection failed while sending the HTTP request. Delivery is uncertain; no automatic retry.',
        http_no_response = 'Dreame connection closed without any HTTP reply. Delivery is uncertain; no automatic retry.',
        http_incomplete = 'Dreame HTTP reply was interrupted. Delivery is uncertain; no automatic retry.'}
    return (context and context .. ': ' or '') .. (details[reason] or 'No HTTP response from Dreamehome. Check Wi-Fi, internet and TLS connectivity.')
end

function Dreamehome.new(config, request, save, clock)
    clock = clock or os.time
    return setmetatable({config = config, request = request, save = save or function()return true end,
        clock = clock, id = math.random(1, 100)}, {__index = Dreamehome})
end

function Dreamehome:base()
    if not regions[self.config.region] then return nil, 'Choose a Dreamehome region: eu, us, cn, sg or ru.' end
    return 'https://' .. self.config.region .. '.iot.dreame.tech:13267'
end

function Dreamehome:headers(content_type)
    local user = self.config.username or ''
    return {['content-type'] = content_type, ['authorization'] = AUTH,
        ['tenant-id'] = self.config.tenant_id or '000000', ['accept-encoding'] = 'identity',
        ['user-agent'] = 'Dart/3.9 (dart:io)',
        ['dreame-meta'] = 'cv=a_102060300;canvasHash=' .. md5(user .. 'c'):sub(1, 8)
            .. ';webglHash=' .. md5(user .. 'w'):sub(1, 8) .. ';visitorIdHash=' .. md5(user .. CID)}
end

function Dreamehome:login(username, password)
    local base, err = self:base(); if not base then return nil, err end
    local body
    if username and password then
        self.config.username = username
        body = 'grant_type=password&scope=all&platform=ANDROID&type=account&username='
            .. quote(username) .. '&password=' .. md5(password .. SALT)
    elseif type(self.config.refresh_token) == 'string' and self.config.refresh_token ~= '' then
        body = 'grant_type=refresh_token&scope=all&platform=ANDROID&type=account&refresh_token='
            .. quote(self.config.refresh_token)
    else return nil, 'Connect your Dreamehome account first.' end
    local status, response, reason = self.request(base .. '/dreame-auth/oauth/token',
        self:headers('application/x-www-form-urlencoded'), body)
    if not status then return nil, connectionError(reason, 'Sign-in / session refresh') end
    if status == 429 then return nil, 'Dreamehome rate limit (HTTP 429). Wait before trying again.' end
    if status == 400 or status == 401 or status == 403 then
        return nil, 'Dreamehome rejected sign-in (HTTP ' .. status .. '). Check the email, Dreamehome password, region and account verification.'
    end
    if status ~= 200 then return nil, 'Dreamehome sign-in service returned HTTP ' .. tostring(tonumber(status) or 0) .. '. Try again later.' end
    local token = decode(response)
    if not token or type(token.access_token) ~= 'string'
        or type(token.refresh_token) ~= 'string' then
        return nil, 'Dreamehome returned an unexpected sign-in response (HTTP 200). The cloud protocol needs checking.'
    end
    self.config.access_token = token.access_token
    self.config.refresh_token = token.refresh_token
    self.config.expires_at = self.clock() + (tonumber(token.expires_in) or 0)
    self.config.tenant_id = token.tenant_id or self.config.tenant_id
    if not self.save(self.config) then return nil, 'Could not save the Dreamehome session.' end
    return true
end
-- Dreame signs nested objects differently from top-level scalar values.

local function spliced(obj, top)
    local keys = {}; for k in pairs(obj) do keys[#keys + 1] = k end; table.sort(keys)
    local out = {}
    for _, k in ipairs(keys) do
        local v = obj[k]; local value
        if type(v) == 'table' then
            if type(next(v)) == 'number' or next(v) == nil then
                if top then value = json().encode(v) end
            else local inner = spliced(v, false); value = inner ~= '' and '[' .. inner .. ']' or ']' end
        elseif type(v) == 'boolean' then value = tostring(v)
        elseif top then value = tostring(v)
        else value = json().encode(v) end
        if value then out[#out + 1] = k .. '=' .. value end
    end
    return table.concat(out, '&')
end

function Dreamehome:api(path, params)
    local base, err = self:base(); if not base then return nil, err end
    if not self.config.access_token or (self.config.expires_at or 0) <= self.clock() + 600 then
        local ok; ok, err = self:login(); if not ok then return nil, err end
    end
    local body
    if params then
        local stamp = self.clock() * 1000
        local signed = {}; for k, v in pairs(params) do signed[k] = v end
        signed.sign = md5(spliced(params, true) .. string.format('%.0f', stamp) .. CID)
        signed.timestamp = stamp; body = json().encode(signed)
    end
    local h = self:headers('application/json'); h['dreame-auth'] = self.config.access_token
    local status, response, reason = self.request(base .. '/' .. path, h, body or '')
    if not status then
        local context = 'Cloud request'
        if params and type(params.data) == 'table' then
            context = params.data.method == 'action' and 'Cleaning command' or 'Robot status / shortcuts'
        end
        return nil, connectionError(reason, context)
    end
    if status == 401 then
        self.config.expires_at = 0
        return nil, 'Dreamehome session expired. Try again to refresh the session.'
    end
    local result = decode(response)
    -- Cloud envelopes use 0 or HTTP-style 200; MIOT property/action result
    -- codes are separate and must still be checked for zero by the caller.
    if status ~= 200 then
        return nil, 'Dreamehome returned HTTP ' .. tostring(tonumber(status) or 0) .. '.'
    end
    if not result then return nil, 'Dreamehome returned HTTP 200 with invalid JSON.' end
    local code = tonumber(result.code)
    if code == 80001 then
        return nil, 'Dreame cloud could not get a robot reply (80001). The robot may be offline or the RPC may be unsupported. No automatic retry.'
    end
    if result.success == false or (code ~= 0 and code ~= 200) then
        local label = code and code % 1 == 0 and math.abs(code) <= 999999 and tostring(code) or 'unknown'
        return nil, 'Dreamehome rejected the cloud request (HTTP 200, service code ' .. label .. ').'
    end
    if result.data == nil then return nil, 'Dreamehome accepted the request but returned no data.' end
    return result.data
end

function Dreamehome:devices()
    local data, err = self:api('dreame-user-iot/iotuserbind/device/listV2')
    if not data then return nil, err end
    if type(data.page) ~= 'table' or type(data.page.records) ~= 'table' then
        return nil, 'Dreamehome returned an unexpected device list.'
    end
    return data.page.records
end

function Dreamehome:rpc(method, params)
    local c = self.config
    if not c.did or not Dreamehome.supportedModel(c.model) then
        return nil, 'Select a supported L50 Pro Ultra robot first.'
    end
    local host = c.bind_domain and c.bind_domain:match('^([%w%-]+)%.')
    if not host then return nil, 'Robot routing information is missing. Reconnect the robot.' end
    self.id = self.id % 500000 + 1
    local data, err = self:api('dreame-iot-com-' .. host .. '/device/sendCommand', {
        did = tostring(c.did), id = self.id, data = {did = tostring(c.did), id = self.id, method = method, params = params}})
    if type(data) ~= 'table' or type(data.result) ~= 'table' then
        return nil, err or 'No robot acknowledgement. Check Dreamehome before trying again.'
    end
    return data.result
end
-- Property `did` is a correlation key, distinct from the outer robot did.
-- Match Tasshack's DreameVacuumProperty values: TASK_STATUS=11, SHORTCUTS=52.

function Dreamehome:taskStatus()
    local result, err = self:rpc('get_properties', {{did = '11', siid = 4, piid = 7}})
    if not result then return nil, err end
    local p = result[1]
    if type(p) ~= 'table' or p.code ~= 0 or type(p.value) ~= 'number'
        or p.value < 0 or p.value % 1 ~= 0
        or (p.siid ~= nil and p.siid ~= 4) or (p.piid ~= nil and p.piid ~= 7) then
        return nil, 'Robot task status is unavailable. No cleaning command was sent.'
    end
    return p.value
end

function Dreamehome:shortcuts()
    local result, err = self:rpc('get_properties', {{did = '52', siid = 4, piid = 48}})
    if not result then return nil, err end
    local property = result[1]
    if type(property) ~= 'table' or property.code ~= 0 then return nil, 'Robot shortcuts are unavailable.' end
    local shortcuts = decode(property.value)
    if not shortcuts then return nil, 'Create Kitchen and Dining shortcuts in Dreamehome first.' end
    return shortcuts
end

function Dreamehome:clean(target)
    if target ~= 'all' and target ~= 'kitchen' and target ~= 'dining' then return nil, 'Unknown cleaning target.' end
    local state, err = self:taskStatus()
    if state == nil then return nil, err end
    if state ~= 0 then
        return nil, 'Robot is busy or its state is unknown. Finish the current task in Dreamehome first.'
    end
    local inputs = {{piid = 1, value = 1}}
    if target ~= 'all' then
        local shortcuts, err = self:shortcuts(); if not shortcuts then return nil, err end
        local found
        for _, s in ipairs(shortcuts) do
            if Dreamehome.shortcutName(s) == target then
                if found then return nil, 'Duplicate shortcut names. Keep one ' .. target .. ' shortcut.' end
                found = tonumber(s.id)
                if not found or found % 1 ~= 0 or found < 25 or found > 128 then return nil, 'Invalid shortcut ID.' end
            end
        end
        if not found then return nil, 'Create a shortcut named ' .. (target == 'kitchen' and 'Kitchen' or 'Dining') .. ' in Dreamehome.' end
        inputs = {{piid = 1, value = 25}, {piid = 10, value = tostring(found)}}
    end
    -- Exactly one action per tap. Never retry a cleaning action after a timeout.
    local result, err = self:rpc('action', {did = tostring(self.config.did), siid = 4, aiid = 1, ['in'] = inputs})
    if not result then return nil, err end
    if result.code ~= 0 then return nil, 'The robot rejected the command. Check Dreamehome.' end
    return true
end

return Dreamehome
