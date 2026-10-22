<table>
<tr>
<td width="150">
  <img alt="Fair3R logo" src="https://fair3r.fr/base/images/fair3r_logo.png" width="150">
</td>
<td>

# ckanext-fair3r

![CKAN](https://img.shields.io/badge/CKAN-2.12.0-orange)
![License](https://img.shields.io/badge/license-AGPL--3.0-blue)
[![PyPI](https://img.shields.io/pypi/v/ckanext-fair3r)](https://pypi.org/project/ckanext-fair3r/)

</td>
</tr>
</table>

This extension is made to cuztomize fair3r.fr ckan theme and add features

## Deployment

For a ready-to-run FAIR3R stack with this extension already wired up, see
[fair3r-docker-alt](https://github.com/Phen-ICS/fair3r-docker-alt).

The instructions below are for adding `ckanext-fair3r` to your own existing
CKAN 2.12 instance.

## Installation

To install ckanext-fair3r:

1. Activate your CKAN virtual environment, for example:

     . /usr/lib/ckan/default/bin/activate

2. Install via pip (ckanext-doi must be installed too: this plugin
   customises its DataCite metadata):

    pip install ckanext-fair3r ckanext-doi

   Or, to install from source:

    git clone https://github.com/Phen-ICS/ckanext-fair3r.git
    cd ckanext-fair3r
    pip install -e .

3. Add `fair3r` to the `ckan.plugins` setting in your CKAN
   config file (by default the config file is located at
   `/etc/ckan/default/ckan.ini`).

4. Restart CKAN (e.g. `sudo systemctl restart ckan-web`, or however your
   CKAN web process is run).


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

    git clone https://github.com/Phen-ICS/ckanext-fair3r.git
    cd ckanext-fair3r
    pip install -e .
    pip install -r dev-requirements.txt

## Fix code formating

ruff format .
ruff check . --fix

## Tests

```shell
docker exec -u ckan -it ckan-app pytest --ckan-ini=/plugins/ckanext-fair3r/test.ini /plugins/ckanext-fair3r/ckanext/fair3r/tests
```