// Public tests for TokenBuffer. Uses ad-hoc assertion macros (no GoogleTest).
#include <cstdlib>
#include <iostream>
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

static void test_append_single() {
    TokenBuffer b;
    b.append(42);
    EXPECT(b.size() == 1, "append_single", "size != 1");
    EXPECT(b[0] == 42, "append_single", "b[0] != 42");
    EXPECT(!b.empty(), "append_single", "empty() true after append");
}

static void test_append_batch_order() {
    TokenBuffer b;
    std::vector<TokenId> tokens = {1, 2, 3, 4, 5};
    b.append_many(tokens);
    EXPECT(b.size() == 5, "append_batch_order", "size != 5");
    auto v = b.to_vector();
    bool ok = (v == tokens);
    EXPECT(ok, "append_batch_order", "to_vector() did not match input");
}

static void test_empty_append_is_noop() {
    TokenBuffer b;
    std::vector<TokenId> empty;
    b.append_many(empty);
    EXPECT(b.size() == 0, "empty_append_is_noop", "size != 0");
    EXPECT(b.empty(), "empty_append_is_noop", "empty() false");
}

static void test_clear_preserves_capacity() {
    TokenBuffer b;
    for (int i = 0; i < 32; ++i) {
        b.append(i);
    }
    std::size_t cap_before = b.capacity();
    b.clear();
    EXPECT(b.size() == 0, "clear_preserves_capacity", "size != 0 after clear");
    EXPECT(b.capacity() == cap_before,
           "clear_preserves_capacity",
           "capacity shrank after clear()");
}

static void test_reserve_no_shrink() {
    TokenBuffer b;
    for (int i = 0; i < 16; ++i) {
        b.append(i);
    }
    std::size_t size_before = b.size();
    std::size_t cap_before = b.capacity();
    b.reserve(4);  // smaller than current
    EXPECT(b.size() == size_before, "reserve_no_shrink", "size changed");
    EXPECT(b.capacity() >= cap_before, "reserve_no_shrink", "capacity shrank");
    bool order_ok = true;
    for (int i = 0; i < 16; ++i) {
        if (b[static_cast<std::size_t>(i)] != i) {
            order_ok = false;
            break;
        }
    }
    EXPECT(order_ok, "reserve_no_shrink", "data corrupted after reserve(small)");
}

static void test_append_many_growth_integrity() {
    // Triggers the off-by-one in append_many during growth and verifies all
    // elements come back through to_vector() in order. Under a buggy starter
    // this either corrupts memory or trips a sanitizer.
    TokenBuffer b;
    b.append(7);
    std::vector<TokenId> batch;
    batch.reserve(100);
    for (int i = 0; i < 100; ++i) {
        batch.push_back(static_cast<TokenId>(i));
    }
    b.append_many(batch);
    EXPECT(b.size() == 101, "append_many_growth", "size != 101");
    auto v = b.to_vector();
    bool ok = (v.size() == 101 && v[0] == 7);
    for (std::size_t i = 0; ok && i < 100; ++i) {
        if (v[i + 1] != static_cast<TokenId>(i)) {
            ok = false;
        }
    }
    EXPECT(ok, "append_many_growth", "elements wrong after growth");
}

static void test_append_after_clear() {
    TokenBuffer b;
    b.append(1);
    b.append(2);
    b.clear();
    b.append(9);
    EXPECT(b.size() == 1, "append_after_clear", "size != 1");
    EXPECT(b[0] == 9, "append_after_clear", "b[0] != 9");
}

int main() {
    test_append_single();
    test_append_batch_order();
    test_empty_append_is_noop();
    test_clear_preserves_capacity();
    test_reserve_no_shrink();
    test_append_many_growth_integrity();
    test_append_after_clear();
    if (g_failures != 0) {
        std::cout << "FAILED " << g_failures << " test(s)\n";
        return 1;
    }
    std::cout << "ALL PUBLIC TESTS PASSED\n";
    return 0;
}
