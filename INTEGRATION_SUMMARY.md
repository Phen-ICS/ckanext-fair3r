# CKAN to Fair3R Custom Overlay Integration - Implementation Summary

This document summarizes all the changes made to implement the integration between CKAN and the Fair3R Custom Overlay (FCO) application.

## Changes Made

### 1. CKAN Configuration Updates

**Files Modified:**
- `deploy/ckan-dev.ini`
- `deploy/ckan-demo.ini`
- `deploy/ckan-prod.ini`

**Changes:**
- Added FCO integration configuration settings
- Environment-specific FCO URLs
- Shared secret key configuration
- Integration enable/disable flag

### 2. CKAN Extension (ckanext-fair3r) Updates

**New Files Created:**
- `ckanext/fair3r/blueprints/__init__.py`
- `ckanext/fair3r/blueprints/fco_integration.py`
- `ckanext/fair3r/templates/package/new.html`
- `ckanext/fair3r/templates/header/header.html`
- `test_fco_integration.py`
- `CKAN_FCO_INTEGRATION.md`

**Files Modified:**
- `ckanext/fair3r/plugin.py`

**Key Features Added:**
- FCO integration blueprint with secure token generation
- Dataset creation request interception
- Health check endpoints
- Template overrides for enhanced UX
- Navigation link to FCO dashboard

### 3. Fair3R Custom Overlay Updates

**New Files Created:**
- `fair3r_custom_overlay/blueprints/ckan/__init__.py`
- `fair3r_custom_overlay/blueprints/ckan/integration.py`
- `fair3r_custom_overlay/templates/ckan/create_dataset.html`
- `alembic/versions/add_ckan_integration_fields.py`

**Files Modified:**
- `fair3r_custom_overlay/models/user.py`
- `fair3r_custom_overlay/__init__.py`
- `fair3r_custom_overlay/lib/_config.py`
- `deploy/requirements.txt`

**Key Features Added:**
- CKAN integration blueprint with secure token validation
- Enhanced dataset creation interface
- User management with CKAN integration
- Database schema updates for CKAN fields
- API endpoints for dataset submission

## Implementation Steps

### Step 1: Database Migration

Run the database migration to add CKAN integration fields:

```bash
cd /opt/fair3r-custom-overlay
alembic upgrade head
```

### Step 2: Install Dependencies

Install the ckanapi dependency for FCO:

```bash
cd /opt/fair3r-custom-overlay
pip install ckanapi==4.8
```

### Step 3: Restart Applications

Restart both CKAN and FCO applications:

```bash
# Restart CKAN
sudo service apache2 reload

# Restart FCO (if using Docker)
cd /opt/fair3r-custom-overlay
docker compose restart

# Or restart FCO directly
python fair3r_custom_overlay_app.py
```

### Step 4: Test Integration

Run the integration test script:

```bash
cd /opt/ckan/lib/default/src/ckanext-fair3r
python test_fco_integration.py
```

## Security Implementation

### Token Generation (CKAN Side)

```python
def _generate_secure_token(user_data, shared_secret):
    # Add timestamp and expiration
    user_data['timestamp'] = int(time.time())
    user_data['expires'] = int(time.time()) + 300  # 5 minutes
    
    # JSON encode and base64 encode
    data_json = json.dumps(user_data, sort_keys=True)
    data_encoded = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
    
    # Create HMAC signature
    signature = hmac.new(
        shared_secret.encode('utf-8'),
        data_encoded.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Combine and encode
    token = f"{data_encoded}.{signature}"
    return base64.b64encode(token.encode('utf-8')).decode('utf-8')
```

### Token Validation (FCO Side)

```python
def _validate_secure_token(token, shared_secret):
    # Decode token
    token_data = base64.b64decode(token.encode('utf-8')).decode('utf-8')
    data_encoded, signature = token_data.split('.', 1)
    
    # Verify HMAC signature
    expected_signature = hmac.new(
        shared_secret.encode('utf-8'),
        data_encoded.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        return None
    
    # Decode data and check expiration
    data_json = base64.b64decode(data_encoded.encode('utf-8')).decode('utf-8')
    user_data = json.loads(data_json)
    
    if user_data.get('expires', 0) < time.time():
        return None
    
    return user_data
```

## User Flow

1. **User logs into CKAN**
2. **User clicks "Add Dataset"**
3. **CKAN intercepts request and generates secure token**
4. **User is redirected to FCO with token**
5. **FCO validates token and authenticates user**
6. **User creates dataset using enhanced interface**
7. **Dataset is submitted to CKAN via API**
8. **User can view dataset in CKAN**

## API Endpoints

### CKAN Endpoints
- `GET /dataset/new` - Intercepted by FCO integration
- `GET /dataset/new/ckan` - Direct access to CKAN dataset creation
- `GET /fco/status` - Integration status check

### FCO Endpoints
- `GET /ckan/integration` - Handle CKAN integration requests
- `GET /ckan/create_dataset` - Enhanced dataset creation interface
- `POST /ckan/submit_dataset` - Submit dataset to CKAN
- `GET /ckan/organizations` - Get available organizations
- `GET /ckan/status` - Integration status check

## Configuration Settings

### CKAN Configuration
```ini
ckanext.fair3r.fco_url = http://localhost:8080
ckanext.fair3r.shared_secret = 5#yqsj4de85s6zzjkncwhjciksd
ckanext.fair3r.enable_fco_integration = true
```

### FCO Configuration
```python
SECRET_KEY = '5#yqsj4de85s6zzjkncwhjciksd'
```

## Testing Checklist

- [ ] Database migration applied successfully
- [ ] Dependencies installed (ckanapi)
- [ ] Both applications running
- [ ] Integration test script passes
- [ ] Health check endpoints respond
- [ ] User can access enhanced dataset creation
- [ ] Dataset creation works end-to-end
- [ ] Fallback to standard CKAN interface works
- [ ] Navigation link to FCO dashboard works

## Troubleshooting

### Common Issues

1. **Integration not working**
   - Check configuration settings
   - Verify both applications are running
   - Check application logs

2. **Authentication failures**
   - Verify SECRET_KEY matches
   - Check database migration
   - Review token generation/validation

3. **Dataset creation fails**
   - Check CKAN API token validity
   - Verify user permissions
   - Review API error messages

### Debug Commands

```bash
# Check CKAN status
curl http://localhost:5000/fco/status

# Check FCO status
curl http://localhost:8080/ckan/status

# Test integration
cd /opt/ckan/lib/default/src/ckanext-fair3r
python test_fco_integration.py
```

## Next Steps

1. **Deploy to development environment**
2. **Test with real users**
3. **Monitor logs for issues**
4. **Deploy to demo environment**
5. **Deploy to production environment**
6. **Plan future enhancements**

## Files Changed Summary

### CKAN Core
- 3 configuration files updated with FCO settings

### ckanext-fair3r
- 1 plugin file modified (added blueprint support)
- 6 new files created (blueprints, templates, tests, docs)

### Fair3R Custom Overlay
- 1 model file modified (added CKAN fields)
- 1 config file modified (shared secret)
- 1 requirements file modified (added ckanapi)
- 1 app file modified (registered blueprint)
- 4 new files created (blueprint, template, migration, docs)

Total: 15 files modified/created across 3 applications 