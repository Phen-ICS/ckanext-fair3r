# CKAN Integration System - Complete Documentation

This document provides comprehensive documentation for the integration between CKAN and multiple applications:

1. **Fair3R Custom Overlay (FCO)** - Enhanced dataset creation functionality with shared authentication
2. **Biox** - Phenotyping data management system that exports datasets to CKAN

## Overview

The CKAN integration system allows multiple applications to seamlessly interact with CKAN for dataset management:

### Fair3R Custom Overlay Integration
- **Shared Authentication**: Users authenticated in CKAN are automatically authenticated in FCO
- **Secure Token Transmission**: API tokens and user data are transmitted securely using HMAC signatures
- **Enhanced Dataset Creation**: Modern, user-friendly interface for dataset creation
- **Seamless Redirects**: Users clicking "Add Dataset" in CKAN are redirected to FCO

### Biox Integration
- **Data Export**: Biox exports phenotyping experiment data to CKAN as datasets
- **Automated Workflow**: Experimental data is automatically formatted and uploaded to CKAN
- **Metadata Management**: Rich metadata including genes, experimental conditions, and statistical analysis
- **Resource Management**: Experimental files, reports, and data files are uploaded as CKAN resources

## Overview

The integration allows users to seamlessly create datasets using an enhanced interface in the Fair3R Custom Overlay application while maintaining their authentication state from CKAN. The integration includes:

- **Shared Authentication**: Users authenticated in CKAN are automatically authenticated in FCO
- **Secure Token Transmission**: API tokens and user data are transmitted securely using HMAC signatures
- **Enhanced Dataset Creation**: Modern, user-friendly interface for dataset creation
- **Seamless Redirects**: Users clicking "Add Dataset" in CKAN are redirected to FCO

## Architecture

### Components

#### Fair3R Custom Overlay Integration

1. **CKAN Extension (ckanext-fair3r)**
   - Intercepts dataset creation requests
   - Generates secure tokens with user data
   - Redirects users to FCO
   - Provides health check endpoints

2. **Fair3R Custom Overlay (FCO)**
   - Validates secure tokens from CKAN
   - Creates/updates user records with CKAN data
   - Provides enhanced dataset creation interface
   - Submits datasets back to CKAN via API

3. **Shared Configuration**
   - Common SECRET_KEY for secure token generation/validation
   - Environment-specific FCO URLs
   - Integration enable/disable settings

#### Biox Integration

1. **Biox Application**
   - Phenotyping data management system
   - Experimental data collection and analysis
   - Automated dataset export to CKAN
   - Metadata generation and resource management

2. **CKAN API Integration**
   - Direct API calls using ckanapi library
   - Dataset creation and updates
   - Resource upload and management
   - Organization and group management

3. **Configuration Management**
   - Environment-specific CKAN URLs and API keys
   - OpenBioX platform integration settings
   - Database schema for CKAN dataset tracking

### Security Model

- **HMAC Signatures**: All tokens are signed with a shared secret
- **Time-based Expiration**: Tokens expire after 5 minutes
- **Secure Transmission**: User data is base64 encoded and signed
- **API Token Storage**: CKAN API tokens are stored encrypted in FCO database

## Implementation Summary

### Fair3R Custom Overlay Integration

#### 1. CKAN Configuration Updates

**Files Modified:**
- `deploy/ckan-dev.ini`
- `deploy/ckan-demo.ini`
- `deploy/ckan-prod.ini`

**Changes:**
- Added FCO integration configuration settings
- Environment-specific FCO URLs
- Shared secret key configuration
- Integration enable/disable flag

#### 2. CKAN Extension (ckanext-fair3r) Updates

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

#### 3. Fair3R Custom Overlay Updates

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

## Configuration

### CKAN Configuration

Add the following settings to your CKAN configuration files:

```ini
## Fair3R Custom Overlay Integration Settings ##################################
# FCO application URL for dataset creation redirects
ckanext.fair3r.fco_url = http://localhost:8080
# Shared secret key for secure token transmission (must match FCO SECRET_KEY)
ckanext.fair3r.shared_secret = 5#yqsj4de85s6zzjkncwhjciksd
# Enable FCO integration for dataset creation
ckanext.fair3r.enable_fco_integration = true
```

**Environment-specific URLs:**
- **Development**: `http://localhost:8080`
- **Demo**: `http://serv-ics-fco-d-01`
- **Production**: `http://serv-ics-fco-p-01`

### Biox Configuration

The Biox application is configured with CKAN integration settings in `biox/lib/configs.py`:

```python
# Development Environment
OPENBIOX_URI = 'http://localhost:5000'
OPENBIOX_API_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'

# Production Environment  
OPENBIOX_URI = 'https://www.fair3r.fr'
OPENBIOX_API_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
```

**Environment-specific Settings:**
- **Development**: Local CKAN instance with development API key
- **Demo**: Demo CKAN instance with demo API key
- **Production**: FAIR3R platform (OpenBioX) with production API key

### FCO Configuration

The FCO application uses the same SECRET_KEY as CKAN:

```python
# In fair3r_custom_overlay/lib/_config.py
SECRET_KEY = '5#yqsj4de85s6zzjkncwhjciksd'
```

## Installation

### Step 1: Database Migration

Run the database migration to add CKAN integration fields:

```bash
cd /opt/fair3r-custom-overlay
alembic upgrade head
```

### Step 2: Install Dependencies

Add the ckanapi dependency to FCO:

```bash
pip install ckanapi==4.8
```

### Step 3: Restart Services

Restart both CKAN and FCO applications:

```bash
# Restart CKAN
sudo service apache2 reload

# Restart FCO (if using Docker)
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

## Usage

### For Users

#### Fair3R Custom Overlay Integration

1. **Log into CKAN** with your credentials
2. **Click "Add Dataset"** in the CKAN interface
3. **Automatic Redirect**: You'll be redirected to the enhanced FCO interface
4. **Create Dataset**: Use the enhanced form to create your dataset
5. **Automatic Submission**: The dataset is automatically created in CKAN
6. **Return to CKAN**: You can view your dataset in the standard CKAN interface

#### Biox Integration

1. **Access Biox**: Log into the Biox phenotyping data management system
2. **Create Project**: Set up a new phenotyping project with experimental parameters
3. **Enter Data**: Input experimental data through Biox's data collection interface
4. **Export to CKAN**: Use the "Export to OpenBioX" function in the task interface
5. **Review Metadata**: Verify the automatically generated metadata
6. **Submit Dataset**: The experimental data is automatically uploaded to CKAN
7. **Access in CKAN**: View the dataset in the CKAN/OpenBioX platform

### For Administrators

#### Enable/Disable Integration

To disable the integration temporarily:

```ini
ckanext.fair3r.enable_fco_integration = false
```

#### Health Checks

Check integration status:

- **CKAN Status**: `http://localhost:5000/fco/status`
- **FCO Status**: `http://localhost:8080/ckan/status`

#### Direct Access

Users can access the standard CKAN interface directly:

- **Standard CKAN**: `http://localhost:5000/dataset/new/ckan`
- **FCO Dashboard**: `http://localhost:8080` (link in CKAN header)

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

### Biox CKAN API Integration

Biox uses the CKAN API directly through the `ckanapi` library:

**Dataset Management:**
- `package_create` - Create new datasets
- `package_update` - Update existing datasets
- `package_show` - Retrieve dataset information
- `package_delete` - Delete datasets

**Resource Management:**
- `resource_create` - Upload files as resources
- `resource_update` - Update existing resources
- `resource_delete` - Remove resources

**Organization Management:**
- `organization_show` - Get organization details
- `organization_create` - Create organizations

**Group Management:**
- `group_show` - Get group information
- `member_create` - Add datasets to groups

**User Management:**
- `user_show` - Get user information
- `user_create` - Create users
- `member_create` - Add users as collaborators

## Database Schema

### FCO User Fields

The FCO user table has been extended with CKAN integration fields:

```sql
ALTER TABLE users ADD COLUMN ckan_user_id VARCHAR(100) UNIQUE;
ALTER TABLE users ADD COLUMN ckan_username VARCHAR(100);
ALTER TABLE users ADD COLUMN ckan_api_token VARCHAR(500);
ALTER TABLE users ADD COLUMN ckan_site_url VARCHAR(200);
```

### FCO User Management

- **Automatic Creation**: Users are automatically created in FCO when they first access the integration
- **Token Storage**: CKAN API tokens are stored securely in the FCO database
- **User Linking**: Users are linked by their CKAN user ID for seamless authentication

### Biox CKAN Integration Fields

The Biox database has been extended with CKAN integration fields:

```sql
-- Request table (projects)
ALTER TABLE request ADD COLUMN openbiox_dataset_id VARCHAR(100);

-- Destination table (organizations)
ALTER TABLE destination_ana ADD COLUMN openbiox_organization_id VARCHAR(100);

-- Task table (experiments)
ALTER TABLE task ADD COLUMN openbiox_ressource_id VARCHAR(100);
```

### Biox Dataset Management

- **Dataset Tracking**: Each Biox project can be linked to a CKAN dataset
- **Organization Mapping**: Biox destinations are mapped to CKAN organizations
- **Resource Tracking**: Individual experiments (tasks) can have CKAN resources
- **Metadata Storage**: Rich metadata is generated and stored in CKAN datasets

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

## Security Considerations

### Token Security

- **HMAC Signatures**: All tokens are signed with SHA256 HMAC
- **Time Expiration**: Tokens expire after 5 minutes to prevent replay attacks
- **Secure Storage**: API tokens are stored in the database (consider encryption for production)

### Authentication Flow

1. User authenticates in CKAN
2. CKAN generates secure token with user data
3. User is redirected to FCO with token
4. FCO validates token and authenticates user
5. User can create datasets using their CKAN API token

### Error Handling

- **Invalid Tokens**: Users are redirected to login
- **Expired Tokens**: Users are redirected to login
- **Connection Failures**: Graceful fallback to standard CKAN interface
- **API Errors**: Detailed error messages for debugging

## Testing

### Test Script

Run the integration test script:

```bash
cd /opt/ckan/lib/default/src/ckanext-fair3r
python test_fco_integration.py
```

### Manual Testing

1. **Start both applications**:
   ```bash
   # CKAN
   ckan -c /path/to/ckan.ini run
   
   # FCO
   python fair3r_custom_overlay_app.py
   ```

2. **Test the integration**:
   - Visit `http://localhost:5000/dataset/new`
   - You should be redirected to FCO
   - Create a dataset using the enhanced interface
   - Verify the dataset appears in CKAN

### Health Checks

Check the status of both applications:

```bash
# CKAN status
curl http://localhost:5000/fco/status

# FCO status
curl http://localhost:8080/ckan/status
```

### Testing Checklist

#### Fair3R Custom Overlay Integration

- [ ] Database migration applied successfully
- [ ] Dependencies installed (ckanapi)
- [ ] Both applications running
- [ ] Integration test script passes
- [ ] Health check endpoints respond
- [ ] User can access enhanced dataset creation
- [ ] Dataset creation works end-to-end
- [ ] Fallback to standard CKAN interface works
- [ ] Navigation link to FCO dashboard works

#### Biox Integration

- [ ] Database migrations applied successfully
- [ ] CKAN API configuration correct
- [ ] Biox application running
- [ ] CKAN platform accessible
- [ ] Test dataset export from Biox
- [ ] Verify dataset appears in CKAN
- [ ] Check metadata generation
- [ ] Verify resource upload
- [ ] Test organization mapping
- [ ] Test collaborator management

## Troubleshooting

### Common Issues

1. **Integration not working**
   - Check that `ckanext.fair3r.enable_fco_integration = true`
   - Verify FCO URL is correct
   - Ensure both applications are running

2. **Authentication failures**
   - Check that SECRET_KEY matches in both applications
   - Verify user has valid CKAN API token
   - Check database migration was applied

3. **Dataset creation fails**
   - Verify CKAN API token is valid
   - Check user has permission to create datasets
   - Review CKAN logs for API errors

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

### Logs

Check application logs for errors:

```bash
# CKAN logs
tail -f /var/log/ckan/default/ckan.log

# FCO logs
tail -f /opt/fair3r-custom-overlay/logs/fair3r_custom_overlay.log
```

### Debug Mode

Enable debug mode for detailed error messages:

```ini
# CKAN
debug = true

# FCO (in config)
DEBUG = True
```

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

### Biox Application
- 1 config file modified (added CKAN integration settings)
- 1 model file modified (added CKAN fields)
- 1 main integration file created (openbiox.py)
- 1 metadata library file created (openbiox_lib.py)
- 2 blueprint files modified (task and admin interfaces)
- 3 database migration files created (CKAN integration fields)

**Total: 21 files modified/created across 4 applications**

### Biox Integration

#### 1. Biox Configuration Updates

**Files Modified:**
- `biox/lib/configs.py`

**Changes:**
- Added OpenBioX CKAN platform configuration
- Environment-specific CKAN URLs and API keys
- Integration with FAIR3R platform (OpenBioX)

#### 2. Biox Database Schema Updates

**Migration Files Created:**
- `alembic/versions/befa4dc8b5ef_openbiox_dataset_id.py`
- `alembic/versions/cd41cd4d6a2b_destination_openbiox_organization_id.py`
- `alembic/versions/0f5a797ef865_task_openbiox_ressource_id.py`

**Database Changes:**
- Added `openbiox_dataset_id` to request table
- Added `openbiox_organization_id` to destination_ana table
- Added `openbiox_ressource_id` to task table

#### 3. Biox Application Updates

**Files Modified:**
- `biox/lib/ws/openbiox.py` - Main CKAN API integration
- `biox/lib/openbiox.py` - Metadata and parameter management
- `biox/blueprints/bp_task.py` - Dataset export workflow
- `biox/blueprints/bp_admin.py` - OpenBioX administration interface
- `biox/model/project.py` - Database model updates

**Key Features Added:**
- Automated dataset creation and updates
- Resource upload and management
- Metadata generation from experimental data
- Organization and group management
- Collaborator management
- Dataset access control (public/private)

#### 4. Integration Workflow

**Dataset Export Process:**
1. **Data Collection**: Biox collects phenotyping experimental data
2. **Metadata Generation**: Automatic generation of rich metadata
3. **Dataset Creation**: Creates or updates CKAN dataset
4. **Resource Upload**: Uploads experimental files and reports
5. **Access Control**: Sets dataset visibility (public/private)
6. **Collaboration**: Manages dataset collaborators and groups

**Metadata Management:**
- **Gene Information**: Automatic extraction from project genes
- **Experimental Conditions**: Date ranges, age information, protocols
- **Statistical Analysis**: Reference ranges and statistical results
- **File Resources**: Experimental plans, reports, and data files

## Future Enhancements

### Planned Features

1. **Resource Upload**: Enhanced file upload interface
2. **Metadata Templates**: Pre-defined dataset templates
3. **Bulk Operations**: Create multiple datasets at once
4. **Advanced Validation**: Enhanced data validation
5. **Workflow Management**: Approval workflows for datasets

### Integration Extensions

1. **User Management**: Synchronize user profiles between applications
2. **Organization Management**: Enhanced organization interface
3. **Analytics**: Dataset usage analytics
4. **Notifications**: Email notifications for dataset events

## Next Steps

1. **Deploy to development environment**
2. **Test with real users**
3. **Monitor logs for issues**
4. **Deploy to demo environment**
5. **Deploy to production environment**
6. **Plan future enhancements**

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review application logs for error messages
3. Test with the provided test script
4. Contact the development team with specific error details

## License

This integration is part of the Fair3R project and follows the same licensing terms as the main applications. 