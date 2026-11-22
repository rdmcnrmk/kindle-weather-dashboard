-- English on-demand controls; no background robot requests or power changes.
local Controls = {
    busy = false,
    labels = {'Clean all', 'Kitchen', 'Dining'},
    targets = {'all', 'kitchen', 'dining'},
}
local last_result = 'Ready. Tap a cleaning button or check the connection.'

local function ui()
    return require('ui/uimanager')
end

local function setStatus(text)
    last_result = text
    ui():setDirty('all', 'full')
end

local function setEnabled(enabled)
    G_reader_settings:saveSetting('dreame_controls_enabled', enabled)
    G_reader_settings:flush()
end

local function showModal(widget)
    require('fridge_power').noteActivity()
    widget.modal = true
    ui():show(widget)
end

local function message(text)
    setStatus(text or 'No response received.')
    showModal(require('ui/widget/infomessage'):new{text = text, timeout = 8})
end

local function client(config)
    local store = require('dreame_store')
    return require('dreamehome').new(
        config or store.load(), require('dreame_transport').request, store.save)
end

function Controls.statusLines()
    local lines = {}
    local line = ''
    for word in last_result:gmatch('%S+') do
        if #line + #word + 1 > 64 then
            lines[#lines + 1] = line
            line = ''
            if #lines == 3 then
                lines[3] = lines[3] .. '...'
                return lines
            end
        end
        line = line == '' and word or line .. ' ' .. word
    end
    if line ~= '' then lines[#lines + 1] = line end
    return lines
end

function Controls.enabled()
    return G_reader_settings:readSetting('dreame_controls_enabled') == true
end

function Controls.run(work)
    if Controls.busy then return end
    Controls.busy = true
    local power = require('fridge_power')
    power.holdInteraction(120)
    local settled = false

    local function finish()
        Controls.busy = false
        power.releaseInteraction()
    end

    local function online()
        -- Ignore late or duplicate callbacks: a tap must never start cleaning twice.
        if settled then return end
        settled = true
        local progress = require('ui/widget/infomessage'):new{text = 'Contacting Dreamehome...'}
        showModal(progress)
        ui():forceRePaint()
        local ok = pcall(work)
        ui():close(progress)
        finish()
        if not ok then
            message('Dreamehome could not complete this request. Check the connection and try again.')
        end
    end

    local ok = pcall(function()
        require('weather_utils'):safeGoOnlineToRun(online, function()
            if settled then return end
            settled = true
            finish()
            message('Could not connect to Wi-Fi. No cleaning command was sent.')
        end, true, false)
    end)
    if not ok and not settled then
        settled = true
        finish()
        message('Could not start the Dreamehome connection.')
    end
end

function Controls.press(n)
    if not Controls.targets[n] then return end
    if Controls.busy then return end
    setStatus('Connecting to Dreamehome for ' .. Controls.labels[n] .. '...')
    Controls.run(function()
        local ok, err = client():clean(Controls.targets[n])
        message(ok and 'Command accepted: ' .. Controls.labels[n] .. '.' or err)
    end)
end

function Controls.check()
    if Controls.busy then return end
    setStatus('Checking robot connection and saved shortcuts...')
    Controls.run(function()
        local c = client()
        local state, err = c:taskStatus()
        if state == nil then message(err); return end
        local shortcuts
        shortcuts, err = c:shortcuts()
        if not shortcuts then
            message('Robot connection OK (task status ' .. tostring(state) .. '). Shortcut lookup failed: ' .. err)
            return
        end
        local found = {}
        for _, shortcut in ipairs(shortcuts) do
            local name = require('dreamehome').shortcutName(shortcut)
            if name then found[name] = true end
        end
        message('Connection OK. Kitchen shortcut: ' .. (found.kitchen and 'found' or 'missing')
            .. '. Dining shortcut: ' .. (found.dining and 'found' or 'missing') .. '.')
    end)
end

function Controls.show()
    local dialog
    local buttons = {}
    for n, label in ipairs(Controls.labels) do
        local index = n
        buttons[#buttons + 1] = {{text = label, callback = function()
            ui():close(dialog)
            Controls.press(index)
        end}}
    end
    buttons[#buttons + 1] = {{text = 'Close', callback = function() ui():close(dialog) end}}
    dialog = require('ui/widget/buttondialog'):new{title = 'Dreame L50 Pro Ultra', buttons = buttons}
    showModal(dialog)
end

local function selectRobot(c)
    local store = require('dreame_store')
    local devices, err = c:devices()
    if not devices then message(err); return end
    local rows = {}
    local picker
    for _, device in ipairs(devices) do
        if require('dreamehome').supportedModel(device.model) and device.did and device.bindDomain then
            local selected = device
            rows[#rows + 1] = {{text = device.customName or device.name or device.model, callback = function()
                c.config.did = tostring(selected.did)
                c.config.model = selected.model
                c.config.bind_domain = selected.bindDomain
                if not store.save(c.config) then message('Could not save the selected robot.'); return end
                setEnabled(true)
                ui():close(picker)
                ui():setDirty('all', 'full')
                message('Robot connected. Create Kitchen and Dining shortcuts in Dreamehome, then test the three buttons. Refresh the dashboard to show them.')
            end}}
        end
    end
    if #rows == 0 then message(require('dreamehome').discoveryMessage(devices)); return end
    rows[#rows + 1] = {{text = 'Cancel', callback = function() ui():close(picker) end}}
    picker = require('ui/widget/buttondialog'):new{title = 'Select your robot', buttons = rows}
    showModal(picker)
end

local function authenticate(fields)
    Controls.run(function()
        local c = client({region = fields[3]})
        local ok, err = c:login(fields[1], fields[2])
        fields[2] = nil
        if not ok then message(err); return end
        selectRobot(c)
    end)
end

function Controls.discover()
    Controls.run(function() selectRobot(client()) end)
end

function Controls.connect()
    if Controls.busy then return end
    local power = require('fridge_power')
    local function active()
        power.noteActivity()
        power.holdInteraction(300)
    end
    local function cancel(dialog)
        ui():close(dialog)
        power.releaseInteraction()
    end
    active()
    local old = require('dreame_store').load()
    local email = old.username or ''
    local region = old.region or 'eu'
    local showEmail, showPassword

    local function show(dialog)
        active()
        showModal(dialog)
        dialog:onShowKeyboard()
        -- Paint the form as well as its separate keyboard widget.
        ui():setDirty('all', 'full')
    end

    showPassword = function()
        local dialog
        dialog = require('ui/widget/inputdialog'):new{
            title = 'Password · Step 2 of 2\n' .. email .. ' · ' .. region:upper(),
            input = '', input_hint = 'Enter your Dreamehome password', text_type = 'password',
            fullscreen = true, condensed = true, allow_newline = false,
            edited_callback = active,
            input_face = require('ui/font'):getFace('infofont', 26),
            buttons = {{
                {text = 'Cancel', id = 'close', callback = function() cancel(dialog) end},
                {text = 'Back', callback = function() ui():close(dialog); showEmail() end},
                {text = 'Connect', is_enter_default = true, callback = function()
                    local password = dialog:getInputText()
                    if password == '' then message('Enter your Dreamehome password.'); return end
                    ui():close(dialog)
                    authenticate({email, password, region})
                end},
            }},
        }
        show(dialog)
    end

    showEmail = function()
        local dialog
        local function nextStep()
            local value = dialog:getInputText():match('^%s*(.-)%s*$')
            if value == '' then message('Enter your Dreamehome account email.'); return end
            email = value
            ui():close(dialog)
            showPassword()
        end
        local function chooseRegion()
            active()
            email = dialog:getInputText()
            ui():close(dialog)
            local picker
            local rows = {}
            for _, item in ipairs({
                {'eu', 'Europe / Netherlands'}, {'us', 'United States'},
                {'cn', 'China'}, {'sg', 'Singapore'}, {'ru', 'Russia'},
            }) do
                local code = item[1]
                rows[#rows + 1] = {{text = item[2] .. ' (' .. code:upper() .. ')', callback = function()
                    region = code
                    ui():close(picker)
                    showEmail()
                end}}
            end
            rows[#rows + 1] = {{text = 'Back', callback = function() ui():close(picker); showEmail() end}}
            picker = require('ui/widget/buttondialog'):new{title = 'Dreamehome account region', buttons = rows}
            showModal(picker)
        end
        dialog = require('ui/widget/inputdialog'):new{
            title = 'Email address · Step 1 of 2',
            input = email, input_hint = 'you@example.com',
            fullscreen = true, condensed = true, allow_newline = false,
            edited_callback = active,
            input_face = require('ui/font'):getFace('infofont', 26),
            buttons = {{
                {text = 'Cancel', id = 'close', callback = function() cancel(dialog) end},
                {text = 'Region: ' .. region:upper(), callback = chooseRegion},
                {text = 'Next', is_enter_default = true, callback = nextStep},
            }},
        }
        show(dialog)
    end
    showEmail()
end

function Controls.disconnect()
    if not require('dreame_store').clear() then message('Could not remove the saved session.'); return end
    setEnabled(false)
    message('Dreamehome disconnected. Refresh the dashboard to hide the buttons.')
end

return Controls
