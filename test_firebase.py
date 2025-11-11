import requests

API_KEY = "AIzaSyDccdzFwGCITQRpBldYiHDNnplCJVNVIQk"
PROJECT_ID = "health-app-7a8b0"
USER_ID = "7BEkGFoyTtgdrrDc3Wp4AmFoLNH3"

# Collection names
USER_COLLECTION = "users"
PERSONAL_COLLECTION = "personalDetails"
MED_COLLECTION = "medicines"

base_url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

def get_collection_data(collection):
    """Fetch all documents from a Firestore collection."""
    url = f"{base_url}/{collection}?key={API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('documents', [])

    else:
        print(f"Error fetching {collection}: {response.status_code}, {response.text}")
        return []

def find_user_documents(collection, user_id):
    """Find documents in a collection that match the given user_id."""
    all_docs = get_collection_data(collection)
   
    user_docs = []
    for doc in all_docs:
        fields = doc.get('fields', {})
        if 'userId' in fields and fields['userId'].get('stringValue') == user_id:
            user_docs.append(doc)
    return user_docs

# Get user-related documents from each collection
user_info = find_user_documents(USER_COLLECTION, USER_ID)
personal_info = find_user_documents(PERSONAL_COLLECTION, USER_ID)
medicines_info = find_user_documents(MED_COLLECTION, USER_ID)

# Display results
print("\n=== USER INFO ===")
for doc in user_info:
    print(doc)

print("\n=== PERSONAL DETAILS ===")
for doc in personal_info:
    print(doc)

print("\n=== MEDICINES ===")
for doc in medicines_info:
    print(doc)


