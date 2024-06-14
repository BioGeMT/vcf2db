# vcf2db

## Overview


### How it works?


### Output


### Important notes

Create a postgres login using the following SQL statement:

&emsp;CREATE ROLE user WITH<br/>
&emsp;&emsp;LOGIN<br/>
&emsp;&emsp;SUPERUSER<br/>
&emsp;&emsp;CREATEDB<br/>
&emsp;&emsp;CREATEROLE<br/>
&emsp;&emsp;INHERIT<br/>
&emsp;&emsp;NOREPLICATION<br/>
&emsp;&emsp;BYPASSRLS<br/>
&emsp;&emsp;CONNECTION LIMIT -1<br/>
&emsp;&emsp;PASSWORD 'password';<br/>

Change _user_ to a user login and the associated _password_.

## Examples
### Command line execution examples:
- ./vcf2db -i your_snp_vcf_file.vcf -d vcf2db -u user -p password -l localhost -b 1000 -c

#### Multi-core execution
  

## Requirements
### Recommended system requirements:
* 8-Core CPU
* 16 GB RAM

### Minimum system requirements:
* Quad-Core CPU
* 8 GB RAM

### Python requirements
* Python 3.10, 3.11 -- see http://www.python.org

### Python dependencies


### Installation
To install the application from package: python setup.py install

## Application structure
* README.md -- This file
* LICENSE.md -- Application license model.
* MANIFEST.in -- Configures which files to include in releases.
* setup.py -- Installation file.
* src/ -- Source Directory
* src/vcf2db.py -- Main orchestrator and application launch file.

## Additional resources


### To package application
python setup.py sdist

### TODO
