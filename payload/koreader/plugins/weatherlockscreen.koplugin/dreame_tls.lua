-- Hostname checks for LuaSec builds without certificate:checkhost().
-- Only used AFTER ssl.wrap(verify='peer') and a successful TLS handshake.
-- Accept DNS subjectAltName entries only; no Common Name fallback.
local Hostname = {}

local function validDNS(name)
    if type(name) ~= 'string' or #name == 0 or #name > 253 then return false end
    if name:find('[^a-z0-9.%-]') or name:find('..', 1, true)
        or name:sub(1, 1) == '.' or name:sub( - 1) == '.' then return false end
    for label in name:gmatch('[^.]+') do
        if #label > 63 or label:sub(1, 1) == '-' or label:sub( - 1) == '-' then return false end
    end
    return true
end

local function matches(name, host)
    if type(name) ~= 'string' then return false end
    name = name:lower()
    if name:sub(1, 2) == '*.' then
        local suffix = name:sub(3)
        if not validDNS(suffix) or not suffix:find('.', 1, true) then return false end
        -- Wildcards cover precisely one complete, nonempty DNS label.
        local first, rest = host:match('^([^.]+)%.(.+)$')
        return first ~= nil and rest == suffix
    end
    return validDNS(name) and name == host
end

function Hostname.verify(cert, host)
    if type(host) ~= 'string' then return false, 'tls_hostname' end
    host = host:lower()
    if not validDNS(host) then return false, 'tls_hostname' end
    if type(cert.checkhost) == 'function' then
        local ok, matched = pcall(cert.checkhost, cert, host)
        -- Never override a native mismatch/error with a fallback.
        if ok and matched == true then return true end
        return false, 'tls_hostname'
    end
    if type(cert.extensions) ~= 'function' then return false, 'tls_support' end
    local ok, extensions = pcall(cert.extensions, cert)
    local san = ok and type(extensions) == 'table' and extensions['2.5.29.17']
    local names = type(san) == 'table' and san.dNSName
    if type(names) ~= 'table' then return false, 'tls_hostname' end
    for _, name in ipairs(names) do if matches(name, host) then return true end end
    return false, 'tls_hostname'
end

return Hostname
