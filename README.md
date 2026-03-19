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

## Requirements
### Recommended system requirements:
* 8-Core CPU
* 16 GB RAM

### Minimum system requirements:
* Quad-Core CPU
* 8 GB RAM

### Python requirements
* Python 3.10, 3.11, 3.12 -- see http://www.python.org

### Python dependencies
* psycopg2, cyvcf2

### Installation
#### Using Conda (Recommended)
Create and activate the conda environment:
```bash
conda env create -f environment.yml
conda activate vcf2db
```

#### Running the application
##### To start a Database from scratch and populate with a VCF
```bash
python vcf2db.py -i your_snp_vcf_file.vcf -d vcf2db -u user -p password -l localhost -b 1000 -c
```
##### To update annotations in an existing database
```bash
python vcf2db.py -i your_snp_vcf_file.vcf -d vcf2db -u user -p password -l localhost -a
```
##### To resume an interrupted update
```bash
python vcf2db.py -i your_snp_vcf_file.vcf -d vcf2db -u user -p password -l localhost -a -r
```
##### If VEP fields changed between versions
```bash
python vcf2db.py -i your_snp_vcf_file.vcf -d vcf2db -u user -p password -l localhost -a -f
```

## Application structure
* README.md -- This file
* LICENSE.md -- Application license model.
* MANIFEST.in -- Configures which files to include in releases.
* environment.yml -- Conda environment configuration file.
* src/ -- Source Directory
* src/vcf2db.py -- Main orchestrator and application launch file.
* src/utils/ -- utilities to write files, create sql queries, and vcf related functions.
* src/tools/ -- additional/optional tools to create a genes tables from gtf file and create synthetic gene expression data.

## Additional resources
### Gene table (tools/gen_genes_table.py) 
Create a genes table based on gtf annotations. The genes table is made up of the gene 
name, gene id, gene type, chromosome, start position, end position and strand.<br/><br/>
Example usage: 
* ./gen_genes_table input.gtf --host localhost --database vcf2db --username user --password password
* ./gen_genes_table input.gtf --host localhost --database vcf2db --username user --password password --force-reload
### Synthetic transcriptomics (tools/gen_synthetic_transcriptomics.py) 
Generate a synthetic transcriptomics table for testing purposes.<br/><br/>
Example usage: 
* ./gen_synthetic_transcriptomics --host localhost --database vcf2db --username user --password password --protein-coding-only --seed 25 
* ./gen_synthetic_transcriptomics --host localhost --database vcf2db --username user --password password --protein-coding-only --seed 25 --force-reload

### To package application
python setup.py sdist

### TODO
