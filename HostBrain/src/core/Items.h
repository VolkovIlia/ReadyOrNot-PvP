#pragma once

// Buyable item catalog, loaded from data/items.csv. The same table is cooked into DT_CompItems for
// the client buy menu, so prices shown and prices charged come from one source.

#include "Types.h"

#include <string>
#include <vector>

namespace RonComp
{
    enum class ItemCategory : std::uint8_t
    {
        Pistol,
        Smg,
        Rifle,
        Shotgun,
        Marksman,
        Lmg,
        Melee,
        Armor,
        Grenade,
        Kit,
    };

    // Who may buy an item. Swat/Suspects follow the faction; Attackers/Defenders follow the side
    // (the defuse kit belongs to whoever defends, whatever their faction).
    enum class ItemAccess : std::uint8_t
    {
        Any,
        Swat,
        Suspects,
        Attackers,
        Defenders,
    };

    struct Item
    {
        std::string Id;
        std::string Name;
        ItemCategory Category = ItemCategory::Pistol;
        ItemAccess Access = ItemAccess::Any;
        int Price = 0;
        int KillReward = 0;
        int MaxCarry = 1;
        std::string GameItem; // Unreal class path the adapters give to the player
    };

    class ItemCatalog
    {
    public:
        // Parses the CSV (header row required). Returns one message per bad row; good rows still load.
        std::vector<std::string> LoadFromCsv(const std::string& text);

        const Item* Find(const std::string& id) const;
        const Item* FindByGameItem(const std::string& gameItem) const;
        const std::vector<Item>& All() const { return m_Items; }

    private:
        std::vector<Item> m_Items;
    };

    bool ParseItemCategory(const std::string& text, ItemCategory& out);
    bool ParseItemAccess(const std::string& text, ItemAccess& out);
    const char* ToString(ItemCategory category);
}
