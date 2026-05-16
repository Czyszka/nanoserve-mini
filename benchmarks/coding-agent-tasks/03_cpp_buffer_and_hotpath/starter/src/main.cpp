#include <iostream>

#include "token_buffer.h"

int main() {
    TokenBuffer buf;
    buf.append(1);
    buf.append(2);
    buf.append(3);
    std::cout << "size=" << buf.size() << "\n";
    return 0;
}
