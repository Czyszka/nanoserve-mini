#include <chrono>
#include <iostream>
#include <vector>

#include "token_buffer.h"

int main() {
    constexpr std::size_t kBatch = 100000;
    constexpr int kIters = 10;

    std::vector<TokenId> tokens;
    tokens.reserve(kBatch);
    for (std::size_t i = 0; i < kBatch; ++i) {
        tokens.push_back(static_cast<TokenId>(i));
    }

    TokenBuffer buf;
    auto t0 = std::chrono::steady_clock::now();
    for (int it = 0; it < kIters; ++it) {
        buf.append_many(tokens);
    }
    auto t1 = std::chrono::steady_clock::now();
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(t1 - t0).count();
    std::cout << "append_many " << kIters << " x " << kBatch
              << " tokens: " << ms << " ms (final size=" << buf.size() << ")\n";
    return 0;
}
