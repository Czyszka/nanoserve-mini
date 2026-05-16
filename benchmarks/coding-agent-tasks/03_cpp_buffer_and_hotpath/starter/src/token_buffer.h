#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>

using TokenId = int32_t;

class TokenBuffer {
public:
    TokenBuffer();
    explicit TokenBuffer(std::size_t initial_capacity);

    void append(TokenId token);
    void append_many(const std::vector<TokenId>& tokens);
    void clear();
    void reserve(std::size_t capacity);

    std::size_t size() const noexcept;
    std::size_t capacity() const noexcept;
    bool empty() const noexcept;

    TokenId operator[](std::size_t index) const;
    std::vector<TokenId> to_vector() const;

    // copy/move declared so we can plant bugs
    TokenBuffer(const TokenBuffer& other);
    TokenBuffer& operator=(const TokenBuffer& other);
    TokenBuffer(TokenBuffer&& other) noexcept;
    TokenBuffer& operator=(TokenBuffer&& other) noexcept;
    ~TokenBuffer();

private:
    TokenId* data_;
    std::size_t size_;
    std::size_t capacity_;
};
