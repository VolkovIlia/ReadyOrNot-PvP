#include "Settings.h"

#include <cmath>
#include <sstream>
#include <stdexcept>

namespace RonComp
{
    Settings::Settings()
    {
        // Match structure
        Register("mp_maxrounds", 24, 2, 60, "Regulation rounds; sides swap after half of them");
        Register("mp_match_can_clinch", 1, 0, 1, "End the match as soon as a team cannot be caught");
        Register("mp_overtime_enable", 1, 0, 1, "Play overtime when regulation ends tied");
        Register("mp_overtime_maxrounds", 6, 2, 30, "Rounds per overtime; sides swap after half of them");
        Register("mp_overtime_startmoney", 12500, 0, 100000, "Money at the start of each overtime half");
        Register("mp_warmuptime", 60, 0, 3600, "Warmup length in seconds");
        Register("mp_freezetime", 15, 0, 120, "Freeze time in seconds");
        Register("mp_roundtime", 1.92, 0.1, 60, "Round length in minutes");
        Register("mp_c4timer", 40, 5, 120, "Seconds from plant to explosion");
        Register("mp_buytime", 20, 0, 300, "Seconds of live round during which buying is still allowed");
        Register("mp_round_restart_delay", 7, 0, 60, "Seconds between round end and the next round");
        Register("mp_halftime_duration", 15, 0, 300, "Halftime break in seconds");
        Register("mp_plant_time", 3.2, 0, 30, "Seconds to plant (applied by the bomb adapter)");
        Register("mp_defuse_time", 10, 0, 60, "Seconds to defuse without a kit (applied by the bomb adapter)");
        Register("mp_defuse_kit_time", 5, 0, 60, "Seconds to defuse with a kit (applied by the bomb adapter)");

        // Teams
        Register("mp_attackers_faction", 0, 0, 1, "0 = suspects attack and SWAT defends; 1 = SWAT attacks");
        Register("mp_team0_starts_attacking", 1, 0, 1, "Team 0 plays the attacking side in the first half");
        Register("mp_friendlyfire", 1, 0, 1, "Friendly fire (applied by the damage adapter)");
        Register("ff_damage_reduction_bullets", 0.33, 0, 1, "Friendly bullet damage multiplier");

        // Money
        Register("mp_startmoney", 800, 0, 100000, "Money at the start of each regulation half");
        Register("mp_maxmoney", 16000, 0, 1000000, "Money cap");
        Register("mp_starting_losses", 1, 0, 10, "Loss counter at the start of each half");
        Register("mp_loss_bonus_max_losses", 5, 1, 20, "Cap of the loss counter");
        Register("mp_loss_bonus_decrement_on_win", 1, 0, 1, "1 = a win lowers the loss counter by one; 0 = resets it");
        Register("mp_attackers_survivor_no_bonus", 1, 0, 1, "Attackers alive when time runs out get no loss bonus");
        Register("mp_warmup_money", 16000, 0, 1000000, "Money during warmup");

        Register("cash_team_elimination", 3250, -100000, 100000, "Team reward for winning by elimination");
        Register("cash_team_win_by_time", 3250, -100000, 100000, "Defenders' reward when time runs out");
        Register("cash_team_attackers_win_bomb", 3500, -100000, 100000, "Attackers' reward when the bomb explodes");
        Register("cash_team_defenders_win_defuse", 3500, -100000, 100000, "Defenders' reward for a defuse");
        Register("cash_team_loser_bonus", 1400, -100000, 100000, "First step of the loss bonus ladder");
        Register("cash_team_loser_bonus_step", 500, -100000, 100000, "Loss bonus increase per extra loss");
        Register("cash_team_planted_bomb_but_lost", 800, -100000, 100000, "Extra for each attacker when the bomb was planted but the round lost");
        Register("cash_team_defenders_per_kill", 0, -100000, 100000, "Team reward to all defenders per attacker killed");
        Register("cash_player_bomb_planted", 300, -100000, 100000, "Planter reward");
        Register("cash_player_bomb_defused", 300, -100000, 100000, "Defuser reward");
        Register("cash_player_killed_teammate", -300, -100000, 100000, "Team kill penalty");
        Register("cash_player_killed_enemy_default", 300, -100000, 100000, "Kill reward for weapons missing from items.csv");

        // Inventory and stats
        Register("mp_max_grenades", 4, 0, 20, "Total grenades a player may carry");
        Register("mp_assist_damage_threshold", 41, 1, 1000, "Minimum damage to a victim that counts as an assist");
        Register("mp_damage_cap_per_victim", 100, 1, 10000, "Damage per victim per round that counts toward stats (their health)");
    }

    void Settings::Register(const std::string& name, double defaultValue, double minValue, double maxValue, const char* help)
    {
        Definition& definition = m_Definitions[name];
        definition.Value = defaultValue;
        definition.Default = defaultValue;
        definition.Min = minValue;
        definition.Max = maxValue;
        definition.Help = help;
    }

    bool Settings::Has(const std::string& name) const
    {
        return m_Definitions.find(name) != m_Definitions.end();
    }

    double Settings::Get(const std::string& name) const
    {
        const auto it = m_Definitions.find(name);
        if (it == m_Definitions.end())
        {
            throw std::invalid_argument("Unknown cvar: " + name);
        }
        return it->second.Value;
    }

    int Settings::GetInt(const std::string& name) const
    {
        return static_cast<int>(std::lround(Get(name)));
    }

    bool Settings::GetBool(const std::string& name) const
    {
        return Get(name) != 0.0;
    }

    bool Settings::Set(const std::string& name, double value, std::string* error)
    {
        const auto it = m_Definitions.find(name);
        if (it == m_Definitions.end())
        {
            if (error) *error = "unknown cvar '" + name + "'";
            return false;
        }
        Definition& definition = it->second;
        if (!std::isfinite(value) || value < definition.Min || value > definition.Max)
        {
            if (error)
            {
                std::ostringstream message;
                message << name << " = " << value << " is outside [" << definition.Min << ", " << definition.Max << "]";
                *error = message.str();
            }
            return false;
        }
        definition.Value = value;
        return true;
    }

    std::vector<std::string> Settings::LoadFromText(const std::string& text)
    {
        std::vector<std::string> errors;
        std::istringstream lines(text);
        std::string line;
        int lineNumber = 0;
        while (std::getline(lines, line))
        {
            ++lineNumber;
            const auto comment = line.find("//");
            if (comment != std::string::npos)
            {
                line.erase(comment);
            }

            std::istringstream tokens(line);
            std::string name;
            if (!(tokens >> name))
            {
                continue; // blank or comment-only line
            }

            std::string valueText;
            std::string extra;
            if (!(tokens >> valueText) || (tokens >> extra))
            {
                errors.push_back("line " + std::to_string(lineNumber) + ": expected '<cvar> <value>'");
                continue;
            }

            double value = 0.0;
            try
            {
                std::size_t consumed = 0;
                value = std::stod(valueText, &consumed);
                if (consumed != valueText.size())
                {
                    throw std::invalid_argument(valueText);
                }
            }
            catch (const std::exception&)
            {
                errors.push_back("line " + std::to_string(lineNumber) + ": '" + valueText + "' is not a number");
                continue;
            }

            std::string error;
            if (!Set(name, value, &error))
            {
                errors.push_back("line " + std::to_string(lineNumber) + ": " + error);
            }
        }
        return errors;
    }

    void Settings::ResetToDefaults()
    {
        for (auto& entry : m_Definitions)
        {
            entry.second.Value = entry.second.Default;
        }
    }
}
