import requests
import sys
import json
from datetime import datetime

class PowerCleanServiceAPITester:
    def __init__(self, base_url="https://pro-site-revamp-2.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.inquiry_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, use_auth_param=False):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)
        
        # For admin endpoints, pass token as query parameter
        params = {}
        if self.token and use_auth_param:
            params['authorization'] = f'Bearer {self.token}'
        elif self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, params=params)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=test_headers, params=params)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, params=params)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_get_services(self):
        """Test get services endpoint"""
        success, response = self.run_test("Get Services", "GET", "services", 200)
        if success and 'services' in response:
            services = response['services']
            print(f"   Found {len(services)} services")
            expected_services = ['baureinigung', 'industriereinigung', 'fassadenreinigung']
            for service_id in expected_services:
                if any(s['id'] == service_id for s in services):
                    print(f"   ✓ Service '{service_id}' found")
                else:
                    print(f"   ✗ Service '{service_id}' missing")
        return success

    def test_admin_setup(self):
        """Test admin setup endpoint"""
        return self.run_test("Admin Setup", "POST", "admin/setup", 200)

    def test_admin_login(self):
        """Test admin login and get token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "admin/login",
            200,
            data={"username": "admin", "password": "powerclean2024"}
        )
        if success and 'token' in response:
            self.token = response['token']
            print(f"   ✓ Token received: {self.token[:20]}...")
            return True
        return False

    def test_create_inquiry(self):
        """Create a test inquiry"""
        inquiry_data = {
            "services": ["baureinigung", "fenster-glasreinigung"],
            "name": f"Test User {datetime.now().strftime('%H%M%S')}",
            "email": f"test{datetime.now().strftime('%H%M%S')}@example.com",
            "phone": "+49 123 456789",
            "address": "Teststraße 123, 30657 Hannover",
            "preferred_date": "2024-12-31",
            "preferred_time": "10:00",
            "description": "Test inquiry for automated testing",
            "consent": True
        }
        
        success, response = self.run_test(
            "Create Inquiry",
            "POST",
            "inquiries",
            200,
            data=inquiry_data
        )
        
        if success and 'id' in response:
            self.inquiry_id = response['id']
            print(f"   ✓ Inquiry created with ID: {self.inquiry_id}")
            return True
        return False

    def test_get_admin_inquiries(self):
        """Get all inquiries (admin only)"""
        if not self.token:
            print("❌ No admin token available")
            return False
            
        success, response = self.run_test(
            "Get Admin Inquiries",
            "GET",
            "admin/inquiries",
            200
        )
        
        if success and 'inquiries' in response:
            inquiries = response['inquiries']
            print(f"   Found {len(inquiries)} inquiries")
            return True
        return False

    def test_get_admin_stats(self):
        """Get admin statistics"""
        if not self.token:
            print("❌ No admin token available")
            return False
            
        success, response = self.run_test(
            "Get Admin Stats",
            "GET",
            "admin/stats",
            200
        )
        
        if success:
            expected_keys = ['total', 'neu', 'in_bearbeitung', 'erledigt']
            for key in expected_keys:
                if key in response:
                    print(f"   ✓ Stat '{key}': {response[key]}")
                else:
                    print(f"   ✗ Stat '{key}' missing")
            return True
        return False

    def test_update_inquiry_status(self):
        """Update inquiry status (admin only)"""
        if not self.token or not self.inquiry_id:
            print("❌ No admin token or inquiry ID available")
            return False
            
        success, response = self.run_test(
            "Update Inquiry Status",
            "PATCH",
            f"admin/inquiries/{self.inquiry_id}",
            200,
            data={"status": "in_bearbeitung", "notes": "Test note from automated testing"}
        )
        
        if success and response.get('status') == 'in_bearbeitung':
            print(f"   ✓ Status updated to 'in_bearbeitung'")
            return True
        return False

    def test_delete_inquiry(self):
        """Delete test inquiry (admin only)"""
        if not self.token or not self.inquiry_id:
            print("❌ No admin token or inquiry ID available")
            return False
            
        success, response = self.run_test(
            "Delete Inquiry",
            "DELETE",
            f"admin/inquiries/{self.inquiry_id}",
            200
        )
        
        if success:
            print(f"   ✓ Inquiry {self.inquiry_id} deleted")
            return True
        return False

    def test_invalid_login(self):
        """Test invalid login credentials"""
        success, response = self.run_test(
            "Invalid Login",
            "POST",
            "admin/login",
            401,
            data={"username": "wrong", "password": "wrong"}
        )
        return success

    def test_unauthorized_access(self):
        """Test unauthorized access to admin endpoints"""
        # Temporarily remove token
        temp_token = self.token
        self.token = None
        
        success, response = self.run_test(
            "Unauthorized Access",
            "GET",
            "admin/inquiries",
            401
        )
        
        # Restore token
        self.token = temp_token
        return success

def main():
    print("🚀 Starting PowerCleanService API Tests")
    print("=" * 50)
    
    tester = PowerCleanServiceAPITester()
    
    # Test sequence
    tests = [
        ("Root API", tester.test_root_endpoint),
        ("Get Services", tester.test_get_services),
        ("Admin Setup", tester.test_admin_setup),
        ("Admin Login", tester.test_admin_login),
        ("Create Inquiry", tester.test_create_inquiry),
        ("Get Admin Inquiries", tester.test_get_admin_inquiries),
        ("Get Admin Stats", tester.test_get_admin_stats),
        ("Update Inquiry Status", tester.test_update_inquiry_status),
        ("Delete Inquiry", tester.test_delete_inquiry),
        ("Invalid Login", tester.test_invalid_login),
        ("Unauthorized Access", tester.test_unauthorized_access)
    ]
    
    print(f"\n📋 Running {len(tests)} tests...")
    
    for test_name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
    
    # Print results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())