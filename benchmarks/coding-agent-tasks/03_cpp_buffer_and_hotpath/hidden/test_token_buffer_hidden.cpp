// Hidden tests for TokenBuffer. Ad-hoc assertion style (no GoogleTest).
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>

#include "token_buffer.h"

static int g_failures = 0;

#define EXPECT(cond, name, msg)                                          \
    do {                                                                  \
        if (!(cond)) {                                                    \
            std::cout << "[FAIL] " << (name) << ": " << (msg) << "\n";    \
            ++g_failures;                                                  \
        } else {                                                          \
            std::cout << "[ OK ] " << (name) << "\n";                     \
        }                                                                 \
    } while (0)

static void test_large_append() {
    constexpr std::size_t kN = 100000;
    std::vector<TokenId> tokens;
    tokens.reserve(kN);
    for (std::size_t i = 0; i < kN; ++i) {
        tokens.push_back(static_cast<TokenId>(i));
    }
    TokenBuffer b;
    b.append_many(tokens);
    EXPECT(b.size() == kN, "large_append", "size mismatch");
    bool ok = true;
    for (std::size_t i = 0; i < kN; ++i) {
        if (b[i] != static_cast<TokenId>(i)) {
            ok = false;
            break;
        }
    }
    EXPECT(ok, "large_append", "element value mismatch");
}

static void test_random_op_sequence() {
    std::mt19937 rng(0xC0FFEEu);
    std::uniform_int_distribution<int> op_dist(0, 3);
    std::uniform_int_distribution<int> tok_dist(-1000, 1000);
    std::uniform_int_distribution<int> batch_dist(0, 16);

    TokenBuffer buf;
    std::vector<TokenId> oracle;

    for (int step = 0; step < 1000; ++step) {
        int op = op_dist(rng);
        if (op == 0) {
            TokenId t = static_cast<TokenId>(tok_dist(rng));
            buf.append(t);
            oracle.push_back(t);
        } else if (op == 1) {
            int n = batch_dist(rng);
            std::vector<TokenId> batch;
            batch.reserve(static_cast<std::size_t>(n));
            for (int i = 0; i < n; ++i) {
                TokenId t = static_cast<TokenId>(tok_dist(rng));
                batch.push_back(t);
                oracle.push_back(t);
            }
            buf.append_many(batch);
        } else if (op == 2) {
            buf.clear();
            oracle.clear();
        } else {
            std::size_t cap = static_cast<std::size_t>(batch_dist(rng)) * 8;
            buf.reserve(cap);
        }
    }

    bool ok = (buf.size() == oracle.size());
    for (std::size_t i = 0; ok && i < oracle.size(); ++i) {
        if (buf[i] != oracle[i]) {
            ok = false;
        }
    }
    EXPECT(ok, "random_ops_vs_oracle", "diverged from std::vector oracle");
}

static void test_copy_ctor_is_deep() {
    TokenBuffer a;
    a.append(7);
    TokenBuffer b = a;  // copy
    a.clear();
    EXPECT(b.size() == 1, "copy_ctor_deep", "copy lost size after src.clear()");
    EXPECT(b.size() == 1 && b[0] == 7,
           "copy_ctor_deep",
           "copy element corrupted after src.clear()");
}

static void test_copy_assign_is_deep() {
    TokenBuffer a;
    a.append(11);
    a.append(22);
    TokenBuffer b;
    b.append(99);
    b = a;
    a.clear();
    EXPECT(b.size() == 2, "copy_assign_deep", "size mismatch");
    EXPECT(b.size() == 2 && b[0] == 11 && b[1] == 22,
           "copy_assign_deep",
           "elements corrupted after src.clear()");
}

static void test_move_ctor_leaves_valid_source() {
    TokenBuffer a;
    a.append(5);
    a.append(6);
    TokenBuffer b = std::move(a);
    EXPECT(b.size() == 2 && b[0] == 5 && b[1] == 6,
           "move_ctor",
           "destination contents wrong");
    EXPECT(a.size() == 0, "move_ctor", "moved-from size not 0");
    a.clear();           // must be safe
    a.append(123);       // must be safe + observable
    EXPECT(a.size() == 1 && a[0] == 123,
           "move_ctor",
           "moved-from object not reusable");
}

static void test_append_after_clear_reuses() {
    TokenBuffer b;
    for (int i = 0; i < 10; ++i) {
        b.append(i);
    }
    b.clear();
    b.append(1);
    b.append(2);
    EXPECT(b.size() == 2 && b[0] == 1 && b[1] == 2,
           "append_after_clear",
           "values wrong");
}

static void test_reserve_smaller_no_corruption() {
    TokenBuffer b;
    for (int i = 0; i < 20; ++i) {
        b.append(i * 3);
    }
    b.reserve(2);
    EXPECT(b.size() == 20, "reserve_smaller", "size changed");
    bool ok = true;
    for (int i = 0; i < 20; ++i) {
        if (b[static_cast<std::size_t>(i)] != i * 3) {
            ok = false;
            break;
        }
    }
    EXPECT(ok, "reserve_smaller", "data corrupted");
}

static void test_capacity_boundary() {
    TokenBuffer b(4);
    for (int i = 0; i < 4; ++i) {
        b.append(i);
    }
    EXPECT(b.size() == 4, "capacity_boundary", "size != 4 at boundary");
    b.append(99);  // forces growth
    EXPECT(b.size() == 5 && b[4] == 99,
           "capacity_boundary",
           "growth from full failed");
}

int main() {
    test_large_append();
    test_random_op_sequence();
    test_copy_ctor_is_deep();
    test_copy_assign_is_deep();
    test_move_ctor_leaves_valid_source();
    test_append_after_clear_reuses();
    test_reserve_smaller_no_corruption();
    test_capacity_boundary();
    if (g_failures != 0) {
        std::cout << "FAILED " << g_failures << " hidden test(s)\n";
        return 1;
    }
    std::cout << "ALL HIDDEN TESTS PASSED\n";
    return 0;
}
