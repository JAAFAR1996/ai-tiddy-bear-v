#include "encoding_service.h"
#include <mbedtls/base64.h>

// Service statistics
static unsigned long totalOperations = 0;
static unsigned long totalErrors = 0;

// Internal helpers
namespace {
    bool validateAndTrack(bool condition) {
        totalOperations++;
        if (!condition) {
            totalErrors++;
            Serial.println("❌ Encoding service: Invalid parameters");
        }
        return condition;
    }
    
    size_t calculateDecodedSize(const char* encoded) {
        if (!encoded) return 0;
        size_t len = strlen(encoded);
        if (len == 0) return 0;
        
        // Remove padding for calculation
        while (len > 0 && encoded[len - 1] == '=') {
            len--;
        }
        
        return (len * 3) / 4;
    }
}

// Implementation
unsigned int decodeBase64(const char* encoded, unsigned char* output, size_t output_size) {
    if (!validateAndTrack(encoded != nullptr && output != nullptr && output_size > 0)) {
        return 0;
    }
    
    size_t expectedSize = calculateDecodedSize(encoded);
    if (expectedSize == 0 || expectedSize > output_size) {
        totalErrors++;
        Serial.printf("❌ Encoding service: Buffer too small. Expected: %d, Available: %d\n", 
                     expectedSize, output_size);
        return 0;
    }
    
    try {
        size_t decodedLength = 0;
        int ret = mbedtls_base64_decode(output, output_size, &decodedLength, 
                                       (const unsigned char*)encoded, strlen(encoded));
        if (ret != 0 || decodedLength == 0) {
            totalErrors++;
            Serial.println("❌ Encoding service: Base64 decoding failed");
            return 0;
        }
        return (unsigned int)decodedLength;
    } catch (...) {
        totalErrors++;
        Serial.println("❌ Encoding service: Exception during base64 decoding");
        return 0;
    }
}

std::vector<uint8_t> decodeBase64ToVector(const String& encoded) {
    std::vector<uint8_t> result;
    
    if (!validateAndTrack(!encoded.isEmpty())) {
        return result;
    }
    
    size_t expectedSize = calculateDecodedSize(encoded.c_str());
    if (expectedSize == 0) {
        totalErrors++;
        return result;
    }
    
    std::vector<uint8_t> buffer(expectedSize + 4);
    unsigned int decodedLength = decodeBase64(encoded.c_str(), buffer.data(), buffer.size());
    
    if (decodedLength > 0) {
        result.assign(buffer.begin(), buffer.begin() + decodedLength);
    }
    
    return result;
}

unsigned int calculateBase64EncodedSize(size_t input_length) {
    if (!validateAndTrack(input_length > 0)) {
        return 0;
    }
    return ((input_length + 2) / 3) * 4 + 1;
}

unsigned int encodeBase64(const unsigned char* data, size_t length, unsigned char* output, size_t output_size) {
    if (!validateAndTrack(data != nullptr && output != nullptr && length > 0)) {
        return 0;
    }
    
    try {
        size_t encodedLength = 0;
        int ret = mbedtls_base64_encode(output, output_size, &encodedLength, 
                                       data, length);
        if (ret != 0 || encodedLength == 0) {
            totalErrors++;
            Serial.println("❌ Encoding service: Base64 encoding failed");
            return 0;
        }
        return (unsigned int)encodedLength;
    } catch (...) {
        totalErrors++;
        Serial.println("❌ Encoding service: Exception during base64 encoding");
        return 0;
    }
}

String encodeBase64ToString(const unsigned char* data, size_t length) {
    String result = "";
    
    if (!validateAndTrack(data != nullptr && length > 0)) {
        return result;
    }
    
    unsigned int bufferSize = calculateBase64EncodedSize(length);
    if (bufferSize == 0) {
        return result;
    }
    
    std::vector<unsigned char> buffer(bufferSize);
    unsigned int encodedLength = encodeBase64(data, length, buffer.data(), buffer.size());
    
    if (encodedLength > 0) {
        buffer[encodedLength] = '\0';
        result = String((char*)buffer.data());
    }
    
    return result;
}

bool isValidBase64(const String& encoded) {
    if (!validateAndTrack(!encoded.isEmpty())) {
        return false;
    }
    
    const char* str = encoded.c_str();
    size_t len = encoded.length();
    
    if (len % 4 != 0) return false;
    
    for (size_t i = 0; i < len; i++) {
        char c = str[i];
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || 
              (c >= '0' && c <= '9') || c == '+' || c == '/' || c == '=')) {
            return false;
        }
        if (c == '=' && i < len - 2) return false;
    }
    
    return true;
}

void getEncodingStats(unsigned long& operations_count, unsigned long& errors_count) {
    operations_count = totalOperations;
    errors_count = totalErrors;
}

void resetEncodingStats() {
    totalOperations = 0;
    totalErrors = 0;
    Serial.println("🔄 Encoding service statistics reset");
}