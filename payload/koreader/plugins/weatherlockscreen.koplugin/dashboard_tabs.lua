-- Shared tab and touch geometry in portrait design coordinates.
-- Add future pages to items; the tab bar divides its width automatically.
local Tabs = {items = {{id = 'weather', label = 'Weather'}, {id = 'vacuum', label = 'Vacuum'}}}

function Tabs.point(x, y, w, h)
    local scale = math.min(w / 1072, h / 1448)
    return (x - (w - 1072 * scale) / 2) / scale, (y - (h - 1448 * scale) / 2) / scale
end

function Tabs.tabRect(index)
    local width = 944 / #Tabs.items
    return 64 + (index - 1) * width, 32, width, 96
end

function Tabs.buttonRect(index) return 64, 440 + (index - 1) * 232, 944, 184 end

local function inside(x, y, left, top, width, height)
    return x >= left and x < left + width and y >= top and y < top + height
end

function Tabs.hitTab(x, y)
    for i, item in ipairs(Tabs.items) do
        if inside(x, y, Tabs.tabRect(i)) then return item.id end
    end
end

function Tabs.hitVacuum(x, y)
    for i = 1, 3 do if inside(x, y, Tabs.buttonRect(i)) then return i end end
end

function Tabs.hitConnect(x, y) return inside(x, y, 64, 1152, 944, 104) end

function Tabs.hitCheck(x, y) return inside(x, y, 64, 1120, 944, 72) end

return Tabs
