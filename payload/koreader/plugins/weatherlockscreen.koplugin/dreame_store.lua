-- Private state lives outside the installed payload; updates preserve it.
local SessionStore = {}

function SessionStore.path() return require('datastorage'):getSettingsDir() .. '/dreamehome-session.json' end

function SessionStore.load()
    local f = io.open(SessionStore.path(), 'r'); if not f then return {} end
    local data = f:read(65537); f:close()
    if not data or #data > 65536 then return {} end
    local ok, value = pcall(require('json').decode, data)
    return ok and type(value) == 'table' and value or {}
end

function SessionStore.save(config)
    local path = SessionStore.path()
    require('util').makePath(require('datastorage'):getSettingsDir())
    -- Whitelist fields: never persist a password or server response wholesale.
    local value = {}
    for _, k in ipairs({'username', 'region', 'access_token', 'refresh_token', 'expires_at',
        'tenant_id', 'did', 'model', 'bind_domain'}) do value[k] = config[k] end
    local ok, data = pcall(require('json').encode, value); if not ok then return false end
    local f = io.open(path .. '.tmp', 'w'); if not f then return false end
    -- Kindle user storage may be FAT; chmod is best effort on that filesystem.
    pcall(function()
        local ffi = require('ffi'); ffi.cdef('int chmod(const char *path, unsigned int mode);')
        ffi.C.chmod(path .. '.tmp', 384)
    end)
    local written = f:write(data); local closed = f:close()
    if not written or not closed then os.remove(path .. '.tmp'); return false end
    if not os.rename(path .. '.tmp', path) then os.remove(path .. '.tmp'); return false end
    return true
end

function SessionStore.clear()
    os.remove(SessionStore.path() .. '.tmp')
    local f = io.open(SessionStore.path(), 'r'); if not f then return true end; f:close()
    return os.remove(SessionStore.path()) ~= nil
end

return SessionStore
