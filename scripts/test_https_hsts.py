#!/usr/bin/env python3
"""
🧸 AI TEDDY BEAR - HTTPS & HSTS SECURITY TEST
=============================================

Tests HTTPS enforcement and HSTS implementation:
1. HTTP to HTTPS redirect
2. HSTS headers validation
3. SSL/TLS certificate checks
4. Security headers verification
"""

import requests
import urllib3
import ssl
import socket
from datetime import datetime
from typing import Dict, List, Any, Optional
import json

# Disable SSL warnings for testing self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class HTTPSSecurityTester:
    """Test HTTPS and HSTS implementation."""
    
    def __init__(self, base_url: str = "aiteddybear.com"):
        self.base_url = base_url
        self.test_domains = [
            base_url,
            f"www.{base_url}",
            f"api.{base_url}",
            f"app.{base_url}"
        ]
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': [],
            'overall_pass': True
        }
    
    def test_http_to_https_redirect(self, domain: str) -> Dict[str, Any]:
        """Test HTTP to HTTPS redirect."""
        test_result = {
            'test': 'HTTP to HTTPS Redirect',
            'domain': domain,
            'pass': False,
            'details': {}
        }
        
        try:
            # Test HTTP redirect
            response = requests.get(f"http://{domain}", allow_redirects=False, timeout=10)
            
            if response.status_code in [301, 302, 307, 308]:
                location = response.headers.get('Location', '')
                if location.startswith('https://'):
                    test_result['pass'] = True
                    test_result['details'] = {
                        'status_code': response.status_code,
                        'redirect_to': location,
                        'permanent': response.status_code == 301
                    }
                else:
                    test_result['details'] = {
                        'error': 'Redirect not to HTTPS',
                        'location': location
                    }
            else:
                test_result['details'] = {
                    'error': 'No redirect',
                    'status_code': response.status_code
                }
                
        except Exception as e:
            test_result['details'] = {'error': str(e)}
        
        return test_result
    
    def test_hsts_headers(self, domain: str) -> Dict[str, Any]:
        """Test HSTS headers."""
        test_result = {
            'test': 'HSTS Headers',
            'domain': domain,
            'pass': False,
            'details': {}
        }
        
        try:
            # Test HTTPS endpoint
            response = requests.get(f"https://{domain}", verify=False, timeout=10)
            hsts_header = response.headers.get('Strict-Transport-Security', '')
            
            if hsts_header:
                # Parse HSTS header
                hsts_parts = [part.strip() for part in hsts_header.split(';')]
                max_age = None
                include_subdomains = False
                preload = False
                
                for part in hsts_parts:
                    if part.startswith('max-age='):
                        max_age = int(part.split('=')[1])
                    elif part == 'includeSubDomains':
                        include_subdomains = True
                    elif part == 'preload':
                        preload = True
                
                # Check requirements
                if max_age and max_age >= 31536000:  # At least 1 year
                    test_result['pass'] = True
                    test_result['details'] = {
                        'header': hsts_header,
                        'max_age': max_age,
                        'max_age_years': max_age / 31536000,
                        'includeSubDomains': include_subdomains,
                        'preload': preload,
                        'recommendation': 'Excellent' if max_age >= 63072000 else 'Good'
                    }
                else:
                    test_result['details'] = {
                        'error': 'max-age too short',
                        'max_age': max_age,
                        'required': 31536000
                    }
            else:
                test_result['details'] = {'error': 'No HSTS header found'}
                
        except Exception as e:
            test_result['details'] = {'error': str(e)}
        
        return test_result
    
    def test_security_headers(self, domain: str) -> Dict[str, Any]:
        """Test additional security headers."""
        test_result = {
            'test': 'Security Headers',
            'domain': domain,
            'pass': True,
            'details': {}
        }
        
        required_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': ['strict-origin-when-cross-origin', 'no-referrer'],
            'Content-Security-Policy': None  # Just check existence
        }
        
        try:
            response = requests.get(f"https://{domain}", verify=False, timeout=10)
            
            for header, expected in required_headers.items():
                actual = response.headers.get(header)
                
                if actual:
                    if expected is None:
                        # Just check existence
                        test_result['details'][header] = '✅ Present'
                    elif isinstance(expected, list):
                        # Check if value is in allowed list
                        if any(exp in actual for exp in expected):
                            test_result['details'][header] = f'✅ {actual}'
                        else:
                            test_result['details'][header] = f'❌ {actual} (expected one of: {expected})'
                            test_result['pass'] = False
                    else:
                        # Exact match
                        if expected in actual:
                            test_result['details'][header] = f'✅ {actual}'
                        else:
                            test_result['details'][header] = f'❌ {actual} (expected: {expected})'
                            test_result['pass'] = False
                else:
                    test_result['details'][header] = '❌ Missing'
                    test_result['pass'] = False
                    
        except Exception as e:
            test_result['details'] = {'error': str(e)}
            test_result['pass'] = False
        
        return test_result
    
    def test_ssl_certificate(self, domain: str) -> Dict[str, Any]:
        """Test SSL certificate validity."""
        test_result = {
            'test': 'SSL Certificate',
            'domain': domain,
            'pass': False,
            'details': {}
        }
        
        try:
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect and get certificate
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Check certificate details
                    test_result['details'] = {
                        'subject': dict(x[0] for x in cert['subject']),
                        'issuer': dict(x[0] for x in cert['issuer']),
                        'version': cert['version'],
                        'notBefore': cert['notBefore'],
                        'notAfter': cert['notAfter'],
                        'subjectAltName': [x[1] for x in cert.get('subjectAltName', [])]
                    }
                    
                    # Basic validation
                    test_result['pass'] = True
                    
        except ssl.SSLError as e:
            test_result['details'] = {'error': f'SSL Error: {e}'}
        except Exception as e:
            test_result['details'] = {'error': str(e)}
        
        return test_result
    
    def test_tls_version(self, domain: str) -> Dict[str, Any]:
        """Test TLS version support."""
        test_result = {
            'test': 'TLS Version',
            'domain': domain,
            'pass': False,
            'details': {}
        }
        
        try:
            # Test TLS 1.2 and 1.3
            supported_versions = []
            
            for tls_version in [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3]:
                try:
                    context = ssl.create_default_context()
                    context.minimum_version = tls_version
                    context.maximum_version = tls_version
                    
                    with socket.create_connection((domain, 443), timeout=10) as sock:
                        with context.wrap_socket(sock, server_hostname=domain) as ssock:
                            supported_versions.append(tls_version.name)
                except:
                    pass
            
            test_result['details'] = {
                'supported_versions': supported_versions,
                'tls_1_2': 'TLSv1_2' in supported_versions,
                'tls_1_3': 'TLSv1_3' in supported_versions
            }
            
            # Pass if at least TLS 1.2 is supported
            test_result['pass'] = 'TLSv1_2' in supported_versions
            
        except Exception as e:
            test_result['details'] = {'error': str(e)}
        
        return test_result
    
    def run_all_tests(self):
        """Run all security tests."""
        print("🔒 AI TEDDY BEAR - HTTPS & HSTS SECURITY TEST")
        print("=" * 60)
        
        for domain in self.test_domains:
            print(f"\n📍 Testing domain: {domain}")
            print("-" * 40)
            
            # HTTP to HTTPS redirect
            result = self.test_http_to_https_redirect(domain)
            self.results['tests'].append(result)
            print(f"  HTTP→HTTPS Redirect: {'✅ PASS' if result['pass'] else '❌ FAIL'}")
            if not result['pass']:
                self.results['overall_pass'] = False
            
            # HSTS headers
            result = self.test_hsts_headers(domain)
            self.results['tests'].append(result)
            print(f"  HSTS Headers: {'✅ PASS' if result['pass'] else '❌ FAIL'}")
            if result['pass'] and 'max_age_years' in result['details']:
                print(f"    └─ Max-Age: {result['details']['max_age_years']:.1f} years")
            if not result['pass']:
                self.results['overall_pass'] = False
            
            # Security headers
            result = self.test_security_headers(domain)
            self.results['tests'].append(result)
            print(f"  Security Headers: {'✅ PASS' if result['pass'] else '❌ FAIL'}")
            if not result['pass']:
                self.results['overall_pass'] = False
            
            # SSL certificate
            result = self.test_ssl_certificate(domain)
            self.results['tests'].append(result)
            print(f"  SSL Certificate: {'✅ PASS' if result['pass'] else '❌ FAIL'}")
            
            # TLS version
            result = self.test_tls_version(domain)
            self.results['tests'].append(result)
            print(f"  TLS Version: {'✅ PASS' if result['pass'] else '❌ FAIL'}")
            if result['pass'] and 'supported_versions' in result['details']:
                print(f"    └─ Versions: {', '.join(result['details']['supported_versions'])}")
        
        print("\n" + "=" * 60)
        print(f"🎯 Overall Result: {'✅ PASS' if self.results['overall_pass'] else '❌ FAIL'}")
        
        # Save detailed report
        report_file = f"https_hsts_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return self.results

def main():
    """Main function."""
    # For local testing, you can override the base URL
    import sys
    base_url = sys.argv[1] if len(sys.argv) > 1 else "aiteddybear.com"
    
    tester = HTTPSSecurityTester(base_url)
    results = tester.run_all_tests()
    
    return 0 if results['overall_pass'] else 1

if __name__ == "__main__":
    exit(main())