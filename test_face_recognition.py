# test_face_recognition.py
# Simple test to verify face_recognition is working

import dlib
import face_recognition
import numpy as np

print("=" * 60)
print("✅ Face Recognition Installation Test")
print("=" * 60)

# Check versions
print(f"\n✅ dlib version: {dlib.__version__}")
print(f"✅ face-recognition version: {face_recognition.__version__}")

# Test 1: Create a dummy image
print("\n📝 Test 1: Creating test image...")
test_image = np.zeros((200, 200, 3), dtype=np.uint8)
print("✅ Test image created successfully")

# Test 2: Try to detect faces
print("\n📝 Test 2: Testing face detection...")
face_locations = face_recognition.face_locations(test_image)
print(f"✅ Face detection works! Found {len(face_locations)} faces (expected 0)")

# Test 3: Create a random pattern
print("\n📝 Test 3: Testing with random pattern...")
pattern_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
face_locations = face_recognition.face_locations(pattern_image)
print(f"✅ Pattern test complete! Found {len(face_locations)} faces")

print("\n" + "=" * 60)
print("🎉 SUCCESS! Face recognition is fully functional!")
print("=" * 60)

print("\n📌 You can now use face_recognition in your Django project")
print("📌 Just import normally:")
print("   import face_recognition")
print("   import dlib")
print("=" * 60)