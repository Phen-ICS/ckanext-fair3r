<table>
<tr>
<td width="150">
  <img alt="Fair3R logo" src="https://fair3r.fr/base/images/fair3r_logo.png" width="150">
</td>
<td>

# ckanext-fair3r

![CKAN](https://img.shields.io/badge/CKAN-2.11.5-orange)
![License](https://img.shields.io/badge/license-AGPL--3.0-blue)
[![PyPI](https://img.shields.io/pypi/v/ckanext-fair3r)](https://pypi.org/project/ckanext-fair3r/)

</td>
</tr>
</table>

This extension is made to cuztomize fair3r.fr ckan theme and add features

## Requirements

Compatibility with core CKAN versions:

| CKAN version    | Compatible? |
|-----------------|-------------|
| 2.11.5          | yes         |


## Installation

To install ckanext-fair3r:

1. Activate your CKAN virtual environment, for example:

     . /usr/lib/ckan/default/bin/activate

2. Install via pip:

    pip install ckanext-fair3r
	pip install -r requirements.txt

   Or, to install from source:

    git clone <url-of-this-repository>
    cd ckanext-fair3r
    pip install -e .
	pip install -r requirements.txt

3. Add `fair3r` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/ckan.ini`).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:

     sudo service apache2 reload


## Config settings

    exemple: 

	# The app context (could be DEV, INTEGRATION, VALIDATION, or PRODUCTION)
	ckanext.fair3r.context = DEV

	# Optional. Directory containing fdf_schema.json and i18n/*.json.
	# In DEV Docker this is set automatically from FDF_SCHEMA_LOCAL_PATH
	# (mounted local clone of https://github.com/Phen-ICS/fair3r-fdf-schema).
	# Leave unset on validation / integration / production (cron downloads GitHub).
	# ckanext.fair3r.fdf_schema_dir = /fdf-schema


## Developer installation

To install ckanext-fair3r for development, activate your CKAN virtualenv and
do:

    git clone <url-of-this-repository>
    cd ckanext-fair3r
    python setup.py develop
    pip install -r dev-requirements.txt

## Fix code formating

ruff format .
ruff check . --fix

## Tests

```shell
docker exec -u ckan -it ckan-app pytest --ckan-ini=/plugins/ckanext-fair3r/test.ini /plugins/ckanext-fair3r/ckanext/fair3r/tests
```