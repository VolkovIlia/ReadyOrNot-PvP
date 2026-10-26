#pragma once

// CS-style cvar registry. Every setting the rules read is registered here with its default and
// valid range, so a typo in a config file or a host command is reported instead of silently
// creating a new value.

#include <map>
#include <string>
#include <vector>

namespace RonComp
{
    class Settings
    {
    public:
        struct Definition
        {
            double Value = 0.0;
            double Default = 0.0;
            double Min = 0.0;
            double Max = 0.0;
            std::string Help;
        };

        // Registers every known cvar with the CS2 competitive defaults (mirrors data/competitive.cfg).
        Settings();

        bool Has(const std::string& name) const;

        // Unknown names are programming errors: Get throws std::invalid_argument.
        double Get(const std::string& name) const;
        int GetInt(const std::string& name) const;
        bool GetBool(const std::string& name) const;

        // Returns false (and leaves the value unchanged) for unknown names or out-of-range values.
        bool Set(const std::string& name, double value, std::string* error = nullptr);

        // Parses "name value // comment" lines. Returns one message per bad line; good lines still apply.
        std::vector<std::string> LoadFromText(const std::string& text);

        void ResetToDefaults();

        const std::map<std::string, Definition>& All() const { return m_Definitions; }

    private:
        void Register(const std::string& name, double defaultValue, double minValue, double maxValue, const char* help);

        std::map<std::string, Definition> m_Definitions;
    };
}
