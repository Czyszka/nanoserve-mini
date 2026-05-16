#include "token_buffer.h"

#include <cstring>
#include <utility>

TokenBuffer::TokenBuffer()
    : data_(nullptr), size_(0), capacity_(0) {}

TokenBuffer::TokenBuffer(std::size_t initial_capacity)
    : data_(nullptr), size_(0), capacity_(0) {
    if (initial_capacity > 0) {
        data_ = new TokenId[initial_capacity];
        capacity_ = initial_capacity;
    }
}

TokenBuffer::~TokenBuffer() {
    delete[] data_;
}

void TokenBuffer::append(TokenId token) {
    if (size_ == capacity_) {
        std::size_t new_cap = capacity_ == 0 ? 8 : capacity_ * 2;
        TokenId* new_data = new TokenId[new_cap];
        if (data_ != nullptr) {
            std::memcpy(new_data, data_, size_ * sizeof(TokenId));
            delete[] data_;
        }
        data_ = new_data;
        capacity_ = new_cap;
    }
    data_[size_++] = token;
}

void TokenBuffer::append_many(const std::vector<TokenId>& tokens) {
    if (tokens.empty()) {
        return;
    }
    if (size_ + tokens.size() > capacity_) {
        // Bug 1: tight allocation with no slack and off-by-one write loop below.
        std::size_t new_cap = size_ + tokens.size();
        TokenId* new_data = new TokenId[new_cap];
        if (data_ != nullptr) {
            std::memcpy(new_data, data_, size_ * sizeof(TokenId));
            delete[] data_;
        }
        data_ = new_data;
        capacity_ = new_cap;
    }
    // Bug 1 (cont.): off-by-one — writes one past the end when i == tokens.size().
    for (std::size_t i = 0; i <= tokens.size(); ++i) {
        data_[size_ + i] = tokens[i];
    }
    size_ += tokens.size();
}

void TokenBuffer::clear() {
    // Bug 3: clear() must preserve capacity but this drops storage entirely.
    delete[] data_;
    data_ = nullptr;
    size_ = 0;
    capacity_ = 0;
}

void TokenBuffer::reserve(std::size_t capacity) {
    if (capacity <= capacity_) {
        return;
    }
    TokenId* new_data = new TokenId[capacity];
    if (data_ != nullptr) {
        std::memcpy(new_data, data_, size_ * sizeof(TokenId));
        delete[] data_;
    }
    data_ = new_data;
    capacity_ = capacity;
}

std::size_t TokenBuffer::size() const noexcept {
    return size_;
}

std::size_t TokenBuffer::capacity() const noexcept {
    return capacity_;
}

bool TokenBuffer::empty() const noexcept {
    return size_ == 0;
}

TokenId TokenBuffer::operator[](std::size_t index) const {
    return data_[index];
}

std::vector<TokenId> TokenBuffer::to_vector() const {
    return std::vector<TokenId>(data_, data_ + size_);
}

// Bug 2: shallow copy — both objects end up owning the same pointer.
TokenBuffer::TokenBuffer(const TokenBuffer& other)
    : data_(other.data_), size_(other.size_), capacity_(other.capacity_) {}

TokenBuffer& TokenBuffer::operator=(const TokenBuffer& other) {
    if (this != &other) {
        // Bug 2 (cont.): shallow copy-assign — leaks current data_ and aliases other.
        data_ = other.data_;
        size_ = other.size_;
        capacity_ = other.capacity_;
    }
    return *this;
}

TokenBuffer::TokenBuffer(TokenBuffer&& other) noexcept
    : data_(other.data_), size_(other.size_), capacity_(other.capacity_) {
    other.data_ = nullptr;
    other.size_ = 0;
    other.capacity_ = 0;
}

TokenBuffer& TokenBuffer::operator=(TokenBuffer&& other) noexcept {
    if (this != &other) {
        delete[] data_;
        data_ = other.data_;
        size_ = other.size_;
        capacity_ = other.capacity_;
        other.data_ = nullptr;
        other.size_ = 0;
        other.capacity_ = 0;
    }
    return *this;
}
