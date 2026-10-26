#include "Items.h"

#include <algorithm>
#include <map>
#include <sstream>

namespace RonComp
{
    namespace
    {
        // Minimal RFC 4180 field splitter: commas separate fields, double quotes wrap fields that
        // contain commas, and "" inside quotes is a literal quote.
        std::vector<std::string> SplitCsvLine(const std::string& line)
        {
            std::vector<std::string> fields;
            std::string field;
            bool quoted = false;
            for (std::size_t i = 0; i < line.size(); ++i)
            {
                const char c = line[i];
                if (quoted)
                {
                    if (c == '"' && i + 1 < line.size() && line[i + 1] == '"')
                    {
                        field += '"';
                        ++i;
                    }
                    else if (c == '"')
                    {
                        quoted = false;
                    }
                    else
                    {
                        field += c;
                    }
                }
                else if (c == '"')
                {
                    quoted = true;
                }
                else if (c == ',')
                {
                    fields.push_back(field);
                    field.clear();
                }
                else if (c != '\r')
                {
                    field += c;
                }
            }
            fields.push_back(field);
            return fields;
        }

        bool ParseInt(const std::string& text, int& out)
        {
            try
            {
                std::size_t consumed = 0;
                out = std::stoi(text, &consumed);
                return consumed == text.size();
            }
            catch (const std::exception&)
            {
                return false;
            }
        }
    }

    bool ParseItemCategory(const std::string& text, ItemCategory& out)
    {
        static const std::map<std::string, ItemCategory> names = {
            {"pistol", ItemCategory::Pistol}, {"smg", ItemCategory::Smg}, {"rifle", ItemCategory::Rifle},
            {"shotgun", ItemCategory::Shotgun}, {"marksman", ItemCategory::Marksman}, {"lmg", ItemCategory::Lmg},
            {"melee", ItemCategory::Melee}, {"armor", ItemCategory::Armor}, {"grenade", ItemCategory::Grenade},
            {"kit", ItemCategory::Kit},
        };
        const auto it = names.find(text);
        if (it == names.end()) return false;
        out = it->second;
        return true;
    }

    bool ParseItemAccess(const std::string& text, ItemAccess& out)
    {
        static const std::map<std::string, ItemAccess> names = {
            {"any", ItemAccess::Any}, {"swat", ItemAccess::Swat}, {"suspects", ItemAccess::Suspects},
            {"attackers", ItemAccess::Attackers}, {"defenders", ItemAccess::Defenders},
        };
        const auto it = names.find(text);
        if (it == names.end()) return false;
        out = it->second;
        return true;
    }

    const char* ToString(ItemCategory category)
    {
        switch (category)
        {
        case ItemCategory::Pistol: return "pistol";
        case ItemCategory::Smg: return "smg";
        case ItemCategory::Rifle: return "rifle";
        case ItemCategory::Shotgun: return "shotgun";
        case ItemCategory::Marksman: return "marksman";
        case ItemCategory::Lmg: return "lmg";
        case ItemCategory::Melee: return "melee";
        case ItemCategory::Armor: return "armor";
        case ItemCategory::Grenade: return "grenade";
        case ItemCategory::Kit: return "kit";
        }
        return "?";
    }

    std::vector<std::string> ItemCatalog::LoadFromCsv(const std::string& text)
    {
        std::vector<std::string> errors;
        std::istringstream lines(text);
        std::string line;

        if (!std::getline(lines, line))
        {
            errors.push_back("empty file");
            return errors;
        }

        // Map columns by header name so the CSV can gain columns without breaking the loader.
        const std::vector<std::string> header = SplitCsvLine(line);
        std::map<std::string, std::size_t> column;
        for (std::size_t i = 0; i < header.size(); ++i)
        {
            column[header[i]] = i;
        }
        for (const char* required : {"id", "name", "category", "faction", "price", "kill_reward", "max_carry", "game_item"})
        {
            if (column.find(required) == column.end())
            {
                errors.push_back(std::string("missing column '") + required + "'");
            }
        }
        if (!errors.empty())
        {
            return errors;
        }

        int lineNumber = 1;
        while (std::getline(lines, line))
        {
            ++lineNumber;
            if (line.empty() || line == "\r")
            {
                continue;
            }
            const std::vector<std::string> fields = SplitCsvLine(line);
            const std::string where = "line " + std::to_string(lineNumber) + ": ";
            if (fields.size() < header.size())
            {
                errors.push_back(where + "expected " + std::to_string(header.size()) + " fields, got " + std::to_string(fields.size()));
                continue;
            }

            Item item;
            item.Id = fields[column["id"]];
            item.Name = fields[column["name"]];
            item.GameItem = fields[column["game_item"]];
            bool ok = !item.Id.empty();
            if (!ok) errors.push_back(where + "empty id");
            if (ok && Find(item.Id))
            {
                errors.push_back(where + "duplicate id '" + item.Id + "'");
                ok = false;
            }
            if (ok && !ParseItemCategory(fields[column["category"]], item.Category))
            {
                errors.push_back(where + "unknown category '" + fields[column["category"]] + "'");
                ok = false;
            }
            if (ok && !ParseItemAccess(fields[column["faction"]], item.Access))
            {
                errors.push_back(where + "unknown faction '" + fields[column["faction"]] + "'");
                ok = false;
            }
            if (ok && (!ParseInt(fields[column["price"]], item.Price) || item.Price < 0))
            {
                errors.push_back(where + "bad price '" + fields[column["price"]] + "'");
                ok = false;
            }
            if (ok && !ParseInt(fields[column["kill_reward"]], item.KillReward))
            {
                errors.push_back(where + "bad kill_reward '" + fields[column["kill_reward"]] + "'");
                ok = false;
            }
            if (ok && (!ParseInt(fields[column["max_carry"]], item.MaxCarry) || item.MaxCarry < 1))
            {
                errors.push_back(where + "bad max_carry '" + fields[column["max_carry"]] + "'");
                ok = false;
            }
            if (ok)
            {
                m_Items.push_back(item);
            }
        }
        return errors;
    }

    const Item* ItemCatalog::Find(const std::string& id) const
    {
        const auto it = std::find_if(m_Items.begin(), m_Items.end(), [&](const Item& item) { return item.Id == id; });
        return it == m_Items.end() ? nullptr : &*it;
    }

    const Item* ItemCatalog::FindByGameItem(const std::string& gameItem) const
    {
        const auto it = std::find_if(m_Items.begin(), m_Items.end(), [&](const Item& item) { return item.GameItem == gameItem; });
        return it == m_Items.end() ? nullptr : &*it;
    }
}
