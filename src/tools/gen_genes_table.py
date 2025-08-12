#!/usr/bin/env python3
# ---------------------------------------------------------------------------------------
# Script to create and populate a genes table in PostgreSQL database from GTF annotation files.
#
# Author: Donald Friggieri
# email: dfriggieri@gmail.com
# ---------------------------------------------------------------------------------------

import psycopg2
import gzip
import re
import argparse
import logging
from typing import Dict, List, Tuple, Optional
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GeneTablePopulator:
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize the gene table populator.
        
        Args:
            db_config: Dictionary with database connection parameters
                      {'host', 'database', 'user', 'password', 'port'}
        """
        self.db_config = db_config
        self.connection = None
        self.cursor = None
        # Define which gene types to include
        self.accepted_types = {
            'protein_coding','lncRNA','miRNA',
            'snRNA','snoRNA','rRNA','sRNA',
            'scaRNA','misc_RNA','Mt_tRNA','Mt_rRNA',
            'pseudogene','processed_pseudogene','unprocessed_pseudogene'
        }
    
    def connect_to_db(self):
        """Establish connection to PostgreSQL database."""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self.cursor = self.connection.cursor()
            logger.info("Successfully connected to PostgreSQL database")
        except psycopg2.Error as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            sys.exit(1)
    
    def create_genes_table(self):
        """Create the genes table if it doesn't exist (without indexes)."""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS genes (
            id SERIAL PRIMARY KEY,
            gene_id VARCHAR(255) NOT NULL,
            gene_name VARCHAR(255),
            gene_type VARCHAR(100),
            chromosome VARCHAR(50) NOT NULL,
            start_position INTEGER NOT NULL,
            end_position INTEGER NOT NULL,
            strand CHAR(1),
            UNIQUE(gene_id, chromosome, start_position, end_position)
        );
        """
        
        try:
            self.cursor.execute(create_table_query)
            self.connection.commit()
            logger.info("Genes table created successfully")
        except psycopg2.Error as e:
            logger.error(f"Error creating genes table: {e}")
            self.connection.rollback()
            raise
    
    def create_indices(self):
        """Create indices on the genes table for optimal query performance."""
        create_indexes_query = """
        CREATE INDEX IF NOT EXISTS idx_genes_id ON genes(gene_id);
        CREATE INDEX IF NOT EXISTS idx_genes_name ON genes(gene_name);
        CREATE INDEX IF NOT EXISTS idx_genes_type ON genes(gene_type);
        CREATE INDEX IF NOT EXISTS idx_genes_chr ON genes(chromosome);
        CREATE INDEX IF NOT EXISTS idx_genes_position ON genes(chromosome, start_position, end_position);
        """
        
        try:
            logger.info("Creating indices on genes table...")
            self.cursor.execute(create_indexes_query)
            self.connection.commit()
            logger.info("Indices created successfully")
        except psycopg2.Error as e:
            logger.error(f"Error creating indices: {e}")
            self.connection.rollback()
            raise
    
    def parse_gtf_attributes(self, attributes_str: str) -> Dict[str, str]:
        """
        Parse GTF attributes string into a dictionary.
        
        Args:
            attributes_str: GTF attributes column (column 9)
            
        Returns:
            Dictionary of attribute key-value pairs
        """
        attributes = {}
        # Pattern to match GTF attributes: key "value";
        pattern = r'(\w+)\s+"([^"]+)";?'
        matches = re.findall(pattern, attributes_str)
        
        for key, value in matches:
            attributes[key] = value
        
        return attributes
    
    def extract_gene_info_from_gtf(self, file_path: str) -> List[Tuple[str, Optional[str], Optional[str], str, int, int, str]]:
        """
        Extract gene information from GTF file.
        
        Args:
            file_path: Path to GTF file (can be gzipped)
            
        Returns:
            List of tuples (gene_id, gene_name, gene_type, chromosome, start_pos, end_pos, strand)
        """
        genes = []
        processed_genes = set()  # To avoid duplicates
        
        # Determine if file is gzipped
        open_func = gzip.open if file_path.endswith('.gz') else open
        mode = 'rt' if file_path.endswith('.gz') else 'r'
        
        # Track gene types for debugging
        gene_types_count = {}
        
        try:
            with open_func(file_path, mode) as f:
                for line_num, line in enumerate(f, 1):
                    # Skip comments and empty lines
                    if line.startswith('#') or not line.strip():
                        continue
                    
                    fields = line.strip().split('\t')
                    if len(fields) < 9:
                        continue
                    
                    # Only process gene features (not transcript, exon, CDS, etc.)
                    if fields[2] != 'gene':
                        continue
                    
                    chromosome = fields[0]
                    source = fields[1]  # e.g., HAVANA, ENSEMBL
                    start_pos = int(fields[3])
                    end_pos = int(fields[4])
                    strand = fields[6]
                    attributes_str = fields[8]
                    
                    # Parse attributes
                    attributes = self.parse_gtf_attributes(attributes_str)
                    
                    # Extract gene information
                    gene_id = attributes.get('gene_id')
                    gene_name = attributes.get('gene_name')
                    gene_type = attributes.get('gene_type') or attributes.get('gene_biotype')
                    
                    # Skip if no gene_id (shouldn't happen in proper GTF)
                    if not gene_id:
                        continue
                    
                    # Filter gene types - only include protein coding and well-known RNA genes
                    # Adjust these filters based on what you want to include
                    if gene_type:
                        gene_types_count[gene_type] = gene_types_count.get(gene_type, 0) + 1
                        
                        # Skip if gene type is not in accepted list
                        if gene_type not in self.accepted_types:
                            continue
                    
                    # Skip obvious non-genes (like TEC - To Be Experimentally Confirmed)
                    if gene_type in ['TEC', 'artifact']:
                        continue
                    
                    # Create unique identifier to avoid duplicates
                    # Use gene_id as the primary identifier (ENSEMBL ID)
                    gene_key = (gene_id, chromosome, start_pos, end_pos)
                    if gene_key not in processed_genes:
                        genes.append((gene_id, gene_name, gene_type, chromosome, start_pos, end_pos, strand))
                        processed_genes.add(gene_key)
                    
                    # Log progress
                    if line_num % 10000 == 0:
                        logger.info(f"Processed {line_num} lines, found {len(genes)} unique genes")
        
        except Exception as e:
            logger.error(f"Error reading GTF file: {e}")
            raise
        
        # Log gene type statistics
        logger.info("Gene types found:")
        for gtype, count in sorted(gene_types_count.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {gtype}: {count}")
        
        logger.info(f"Extracted {len(genes)} unique genes from GTF file")
        return genes
    
    def insert_genes(self, genes: List[Tuple[str, Optional[str], Optional[str], str, int, int, str]]):
        """
        Insert gene data into the database.
        
        Args:
            genes: List of tuples (gene_id, gene_name, gene_type, chromosome, start_pos, end_pos, strand)
        """
        insert_query = """
        INSERT INTO genes (gene_id, gene_name, gene_type, chromosome, start_position, end_position, strand)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (gene_id, chromosome, start_position, end_position) 
        DO NOTHING;
        """
        
        try:
            # Clear existing data (optional - comment out if you want to append)
            # self.cursor.execute("TRUNCATE TABLE genes RESTART IDENTITY;")
            
            # Batch insert
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(genes), batch_size):
                batch = genes[i:i + batch_size]
                self.cursor.executemany(insert_query, batch)
                self.connection.commit()
                total_inserted += len(batch)
#                logger.info(f"Inserted {total_inserted}/{len(genes)} genes")
            
            logger.info(f"Successfully inserted {total_inserted} genes into database")
        
        except psycopg2.Error as e:
            logger.error(f"Error inserting genes: {e}")
            self.connection.rollback()
            raise
    
    def close_connection(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed")
    
    def process_annotation_file(self, file_path: str, force_reload: bool = False):
        """
        Process GTF annotation file and populate genes table.
        
        Args:
            file_path: Path to GTF file (can be gzipped)
        """
        logger.info(f"Processing GTF annotation file: {file_path}")
        
        # Validate file format
        if not file_path.lower().endswith(('.gtf', '.gtf.gz')):
            raise ValueError("File must be in GTF format (.gtf or .gtf.gz)")
        
        # Extract gene information from GTF
        genes = self.extract_gene_info_from_gtf(file_path)
        
        if not genes:
            logger.warning("No genes found in the GTF file")
            return
        
        # Connect to database and create table
        self.connect_to_db()

        if force_reload:
            logger.info("Force reload requested - clearing existing data")
            self.cursor.execute("DROP TABLE IF EXISTS genes CASCADE")
            self.connection.commit()
            logger.info("Existing genes table dropped")

        self.create_genes_table()
        
        # Insert genes first (more efficient without indexes)
        self.insert_genes(genes)
        
        # Create indices after data insertion for optimal performance
        self.create_indices()
        
        # Close connection
        self.close_connection()

def main():
    parser = argparse.ArgumentParser(description='Populate genes table from GTF annotation file')
    parser.add_argument('gtf_file', help='Path to GTF annotation file (.gtf or .gtf.gz)')
    parser.add_argument('-l', '--host', default='localhost', help='Database host')
    parser.add_argument('-d', '--database', required=True, help='Database name')
    parser.add_argument('-u','--user', required=True, help='Database user')
    parser.add_argument('-p','--password', required=True, help='Database password')
    parser.add_argument('--port', default='5432', help='Database port')
    parser.add_argument('--force-reload', action='store_true', help='Clear existing data and reload completely')
    
    args = parser.parse_args()
    
    # Database configuration
    db_config = {
        'host': args.host,
        'database': args.database,
        'user': args.user,
        'password': args.password,
        'port': args.port
    }
    
    # Create populator instance and process file
    populator = GeneTablePopulator(db_config)
    
    try:
        populator.process_annotation_file(args.gtf_file, args.force_reload)
        logger.info("Gene table population completed successfully!")
    
    except Exception as e:
        logger.error(f"Failed to populate gene table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
