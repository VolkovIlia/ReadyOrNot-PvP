#pragma once

// Dependency-free test harness: TEST registers a function, CHECK* record failures and keep going,
// REQUIRE* stop the current test. Keeps the core buildable with any C++17 compiler.

#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace TestFramework
{
    struct TestCase
    {
        const char* Name;
        std::function<void()> Body;
    };

    struct RequireFailed
    {
    };

    inline std::vector<TestCase>& Registry()
    {
        static std::vector<TestCase> tests;
        return tests;
    }

    inline int& FailureCount()
    {
        static int failures = 0;
        return failures;
    }

    inline std::string& DataDir()
    {
        static std::string dir = "data";
        return dir;
    }

    inline void ReportFailure(const char* file, int line, const std::string& message)
    {
        ++FailureCount();
        std::cout << "    FAIL " << file << ":" << line << ": " << message << "\n";
    }

    struct Registrar
    {
        Registrar(const char* name, std::function<void()> body)
        {
            Registry().push_back({name, std::move(body)});
        }
    };

    template <typename A, typename B>
    std::string DescribeMismatch(const char* lhs, const char* rhs, const A& a, const B& b)
    {
        std::ostringstream out;
        out << lhs << " == " << rhs << " (" << a << " vs " << b << ")";
        return out.str();
    }
}

#define TF_CONCAT_INNER(a, b) a##b
#define TF_CONCAT(a, b) TF_CONCAT_INNER(a, b)

#define TEST(name)                                                                              \
    static void TF_CONCAT(TestBody_, name)();                                                   \
    static TestFramework::Registrar TF_CONCAT(TestRegistrar_, name)(#name, &TF_CONCAT(TestBody_, name)); \
    static void TF_CONCAT(TestBody_, name)()

#define CHECK(condition)                                                                        \
    do                                                                                          \
    {                                                                                           \
        if (!(condition)) TestFramework::ReportFailure(__FILE__, __LINE__, #condition);         \
    } while (0)

#define CHECK_EQ(lhs, rhs)                                                                      \
    do                                                                                          \
    {                                                                                           \
        const auto& tfA = (lhs);                                                                \
        const auto& tfB = (rhs);                                                                \
        if (!(tfA == tfB))                                                                      \
            TestFramework::ReportFailure(__FILE__, __LINE__, TestFramework::DescribeMismatch(#lhs, #rhs, tfA, tfB)); \
    } while (0)

#define REQUIRE(condition)                                                                      \
    do                                                                                          \
    {                                                                                           \
        if (!(condition))                                                                       \
        {                                                                                       \
            TestFramework::ReportFailure(__FILE__, __LINE__, #condition);                       \
            throw TestFramework::RequireFailed{};                                               \
        }                                                                                       \
    } while (0)
