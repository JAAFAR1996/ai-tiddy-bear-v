#ifndef ENCODING_SERVICE_H
#define ENCODING_SERVICE_H

#include <Arduino.h>
#include <vector>

/**
 * @brief Professional Encoding Service - Clean Interface
 * Solves ODR violations by providing single translation unit for base64 operations
 */

// Decoding functions
unsigned int decodeBase64(const char* encoded, unsigned char* output, size_t output_size);
std::vector<uint8_t> decodeBase64ToVector(const String& encoded);

// Encoding functions  
unsigned int calculateBase64EncodedSize(size_t input_length);
unsigned int encodeBase64(const unsigned char* data, size_t length, unsigned char* output, size_t output_size);
String encodeBase64ToString(const unsigned char* data, size_t length);

// Validation functions
bool isValidBase64(const String& encoded);

// Statistics functions
void getEncodingStats(unsigned long& operations_count, unsigned long& errors_count);
void resetEncodingStats();

#endif // ENCODING_SERVICE_H