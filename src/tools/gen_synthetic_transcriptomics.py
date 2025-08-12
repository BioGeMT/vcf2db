#!/usr/bin/env python3
# ---------------------------------------------------------------------------------------
# Script to generate and populate synthetic transcriptomics data in PostgreSQL database.
#
# Author: Donald Friggieri
# email: dfriggieri@gmail.com
# ---------------------------------------------------------------------------------------


import psycopg2
import argparse
import logging
import numpy as np
from typing import Dict, List, Tuple
import sys
import random

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SyntheticTranscriptomicsGenerator:
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize the synthetic transcriptomics data generator.

        Args:
            db_config: Dictionary with database connection parameters
        """
        self.db_config = db_config
        self.connection = None
        self.cursor = None

        # Parameters for realistic count distributions
        self.expression_profiles = {
            'high': {'mean': 1000, 'std': 300, 'detection_rate': 0.95},
            'medium': {'mean': 200, 'std': 80, 'detection_rate': 0.80},
            'low': {'mean': 30, 'std': 15, 'detection_rate': 0.60},
            'very_low': {'mean': 5, 'std': 3, 'detection_rate': 0.30},
            'not_expressed': {'mean': 0, 'std': 0, 'detection_rate': 0.05}
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

    def create_expression_table(self):
        """Create the gene_expression table if it doesn't exist."""
        create_table_query = """
                             CREATE TABLE IF NOT EXISTS gene_expression (
                                id SERIAL PRIMARY KEY,
                                sample_id INTEGER NOT NULL REFERENCES samples(id) ON DELETE CASCADE,
                                gene_id INTEGER NOT NULL REFERENCES genes(id) ON DELETE CASCADE,
                                raw_count INTEGER NOT NULL DEFAULT 0,
                                normalized_count DECIMAL(10,4),
                                UNIQUE(sample_id, gene_id)
                             ); \
                             """

        try:
            self.cursor.execute(create_table_query)
            self.connection.commit()
            logger.info("Gene expression table created successfully")
        except psycopg2.Error as e:
            logger.error(f"Error creating gene expression table: {e}")
            self.connection.rollback()
            raise

    def create_expression_indices(self):
        """Create indices on the gene_expression table."""
        create_indexes_query = """
                               CREATE INDEX IF NOT EXISTS idx_expression_sample ON gene_expression(sample_id);
                               CREATE INDEX IF NOT EXISTS idx_expression_gene ON gene_expression(gene_id);
                               CREATE INDEX IF NOT EXISTS idx_expression_count ON gene_expression(normalized_count);
                               CREATE INDEX IF NOT EXISTS idx_expression_sample_gene ON gene_expression(sample_id, gene_id); \
                               """

        try:
            logger.info("Creating indices on gene_expression table...")
            self.cursor.execute(create_indexes_query)
            self.connection.commit()
            logger.info("Indices created successfully")
        except psycopg2.Error as e:
            logger.error(f"Error creating indices: {e}")
            self.connection.rollback()
            raise

    def get_sample_ids(self, sample_names: List[str] = None) -> Dict[str, int]:
        """
        Get sample IDs from sample names.

        Args:
            sample_names: List of sample names. If None, get all samples.

        Returns:
            Dictionary mapping sample_name to sample_id
        """
        if sample_names:
            # Get specific samples
            placeholders = ','.join(['%s'] * len(sample_names))
            query = f"""
            SELECT id, sample_name FROM samples 
            WHERE sample_name IN ({placeholders})
            """
            self.cursor.execute(query, sample_names)
        else:
            # Get all samples
            query = "SELECT id, sample_name FROM samples"
            self.cursor.execute(query)

        results = self.cursor.fetchall()
        sample_mapping = {name: sid for sid, name in results}

        # Check if all requested samples were found
        if sample_names:
            missing_samples = set(sample_names) - set(sample_mapping.keys())
            if missing_samples:
                logger.error(f"Sample(s) not found in database: {missing_samples}")
                raise ValueError(f"Missing samples: {missing_samples}")

        logger.info(f"Found {len(sample_mapping)} samples")
        return sample_mapping

    def get_gene_ids(self, protein_coding_only: bool = False) -> List[int]:
        """
        Get gene IDs from the genes table.

        Args:
            protein_coding_only: If True, only return protein coding genes

        Returns:
            List of gene IDs
        """
        if protein_coding_only:
            query = "SELECT id FROM genes WHERE gene_type = 'protein_coding' ORDER BY id"
            gene_type_filter = "protein coding"
        else:
            query = "SELECT id FROM genes ORDER BY id"
            gene_type_filter = "all"

        self.cursor.execute(query)
        gene_ids = [row[0] for row in self.cursor.fetchall()]
        logger.info(f"Found {len(gene_ids)} {gene_type_filter} genes")
        return gene_ids

    def assign_expression_profile(self) -> str:
        """
        Assign expression profile for protein coding genes.

        Returns:
            Expression profile name
        """
        # Optimized for protein coding genes
        return np.random.choice(
            ['high', 'medium', 'low', 'very_low', 'not_expressed'],
            p=[0.20, 0.30, 0.27, 0.18, 0.05]  # Higher expression rates for protein coding
        )

    def generate_realistic_count(self, profile_name: str, add_noise: bool = True) -> int:
        """
        Generate realistic count data based on expression profile.

        Args:
            profile_name: Name of expression profile
            add_noise: Whether to add biological noise

        Returns:
            Count value
        """
        profile = self.expression_profiles[profile_name]

        # Check if gene is detected (expressed) in this sample
        if np.random.random() > profile['detection_rate']:
            return 0

        # Generate base count from log-normal distribution (more realistic for RNA-seq)
        if profile['mean'] > 0:
            # Log-normal distribution parameters
            sigma = np.sqrt(np.log(1 + (profile['std'] / profile['mean'])**2))
            mu = np.log(profile['mean']) - 0.5 * sigma**2

            count = int(np.random.lognormal(mu, sigma))

            # Add biological noise if requested
            if add_noise:
                noise_factor = np.random.normal(1.0, 0.1)  # ±10% biological variation
                count = max(0, int(count * noise_factor))
        else:
            count = 0

        return max(0, count)  # Ensure non-negative

    def add_differential_expression(self, counts: Dict[Tuple[int, int], int],
                                    sample_mapping: Dict[str, int]) -> Dict[Tuple[int, int], int]:
        """
        Add differential expression patterns between sample groups.

        Args:
            counts: Dictionary of (sample_id, gene_id) -> count
            sample_mapping: Dictionary of sample_name -> sample_id

        Returns:
            Modified counts dictionary
        """
        # Get sample groups
        query = """
                SELECT s.id, s.sample_name, s.sample_grp
                FROM samples s
                WHERE s.id IN %s \
                """
        sample_ids = tuple(sample_mapping.values())
        self.cursor.execute(query, (sample_ids,))
        sample_groups = {row[0]: row[2] for row in self.cursor.fetchall()}

        # Get unique groups
        unique_groups = list(set(sample_groups.values()))
        if len(unique_groups) < 2:
            logger.info("Only one sample group found, skipping differential expression")
            return counts

        logger.info(f"Adding differential expression between groups: {unique_groups}")

        # Get all gene IDs
        gene_ids = list(set(gene_id for _, gene_id in counts.keys()))

        # Randomly select genes for differential expression (10-20% of genes)
        n_de_genes = int(len(gene_ids) * np.random.uniform(0.10, 0.20))
        de_genes = np.random.choice(gene_ids, n_de_genes, replace=False)

        logger.info(f"Making {len(de_genes)} genes differentially expressed")

        # Apply fold changes
        for gene_id in de_genes:
            # Random fold change between 1.5x and 8x
            fold_change = np.random.uniform(1.5, 8.0)

            # Randomly choose which group gets upregulated
            upregulated_group = np.random.choice(unique_groups)

            for sample_id in sample_mapping.values():
                if (sample_id, gene_id) in counts:
                    if sample_groups[sample_id] == upregulated_group:
                        # Upregulate
                        counts[(sample_id, gene_id)] = int(counts[(sample_id, gene_id)] * fold_change)
                    else:
                        # Downregulate
                        counts[(sample_id, gene_id)] = int(counts[(sample_id, gene_id)] / fold_change)

        return counts

    def generate_synthetic_data(self, sample_names: List[str] = None,
                                add_differential: bool = True,
                                protein_coding_only: bool = False) -> List[Tuple]:
        """
        Generate synthetic transcriptomics data.

        Args:
            sample_names: List of sample names to generate data for
            add_differential: Whether to add differential expression patterns
            protein_coding_only: If True, only generate data for protein coding genes

        Returns:
            List of tuples (sample_id, gene_id, raw_count, normalized_count)
        """
        gene_filter = "protein coding" if protein_coding_only else "all"
        logger.info(f"Generating synthetic transcriptomics data for {gene_filter} genes...")

        # Get sample and gene information
        sample_mapping = self.get_sample_ids(sample_names)
        gene_ids = self.get_gene_ids(protein_coding_only)

        if not sample_mapping or not gene_ids:
            raise ValueError("No samples or genes found in database")

        # Generate count data
        expression_data = {}
        total_combinations = len(sample_mapping) * len(gene_ids)
        processed = 0

        for sample_name, sample_id in sample_mapping.items():
            logger.info(f"Generating data for sample: {sample_name}")

            for gene_id in gene_ids:
                # Assign expression profile (simplified for protein coding)
                profile = self.assign_expression_profile()

                # Generate count
                count = self.generate_realistic_count(profile)
                expression_data[(sample_id, gene_id)] = count

                processed += 1
                if processed % 10000 == 0:
                    logger.info(f"Generated {processed}/{total_combinations} data points")

        # Add differential expression patterns
        if add_differential:
            expression_data = self.add_differential_expression(expression_data, sample_mapping)

        # Calculate normalization (TPM-like normalization)
        logger.info("Calculating normalized values...")

        # Calculate library sizes (total counts per sample)
        library_sizes = {}
        for sample_id in sample_mapping.values():
            total_counts = sum(count for (sid, _), count in expression_data.items() if sid == sample_id)
            library_sizes[sample_id] = max(total_counts, 1)  # Avoid division by zero

        # Prepare final data
        final_data = []
        for (sample_id, gene_id), raw_count in expression_data.items():
            # Simple TPM-like normalization (counts per million)
            normalized_count = (raw_count / library_sizes[sample_id]) * 1_000_000
            final_data.append((sample_id, gene_id, raw_count, round(normalized_count, 4)))

        logger.info(f"Generated {len(final_data)} expression data points")
        return final_data

    def insert_expression_data(self, expression_data: List[Tuple]):
        """
        Insert expression data into the database.

        Args:
            expression_data: List of tuples (sample_id, gene_id, raw_count, normalized_count)
        """
        insert_query = """
                       INSERT INTO gene_expression (sample_id, gene_id, raw_count, normalized_count)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (sample_id, gene_id)
                           DO UPDATE SET
                                         raw_count = EXCLUDED.raw_count,
                                         normalized_count = EXCLUDED.normalized_count; \
                       """

        try:
            # Batch insert
            batch_size = 5000
            total_inserted = 0

            for i in range(0, len(expression_data), batch_size):
                batch = expression_data[i:i + batch_size]
                self.cursor.executemany(insert_query, batch)
                self.connection.commit()
                total_inserted += len(batch)
                logger.info(f"Inserted {total_inserted}/{len(expression_data)} expression records")

            logger.info(f"Successfully inserted {total_inserted} expression records")

        except psycopg2.Error as e:
            logger.error(f"Error inserting expression data: {e}")
            self.connection.rollback()
            raise

    def generate_expression_summary(self, sample_names: List[str] = None):
        """Generate summary statistics of the created expression data."""
        if sample_names:
            sample_mapping = self.get_sample_ids(sample_names)
            sample_ids = tuple(sample_mapping.values())
            query = """
                    SELECT
                        s.sample_name,
                        s.sample_grp,
                        COUNT(*) as total_measurements,
                        COUNT(CASE WHEN ge.raw_count > 0 THEN 1 END) as expressed_genes,
                        AVG(ge.raw_count) as mean_count,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ge.raw_count) as median_count
                    FROM gene_expression ge
                             JOIN samples s ON ge.sample_id = s.id
                    WHERE s.id IN %s
                    GROUP BY s.id, s.sample_name, s.sample_grp
                    ORDER BY s.sample_name \
                    """
            self.cursor.execute(query, (sample_ids,))
        else:
            query = """
                    SELECT
                        s.sample_name,
                        s.sample_grp,
                        COUNT(*) as total_measurements,
                        COUNT(CASE WHEN ge.raw_count > 0 THEN 1 END) as expressed_genes,
                        AVG(ge.raw_count) as mean_count,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ge.raw_count) as median_count
                    FROM gene_expression ge
                             JOIN samples s ON ge.sample_id = s.id
                    GROUP BY s.id, s.sample_name, s.sample_grp
                    ORDER BY s.sample_name \
                    """
            self.cursor.execute(query)

        results = self.cursor.fetchall()

        logger.info("\nExpression Data Summary:")
        logger.info("-" * 80)
        logger.info(f"{'Sample':<15} {'Group':<10} {'Total':<8} {'Expressed':<10} {'Mean':<8} {'Median':<8}")
        logger.info("-" * 80)

        for row in results:
            sample_name, group, total, expressed, mean_count, median = row
            logger.info(f"{sample_name:<15} {group:<10} {total:<8} {expressed:<10} {mean_count:<8.1f} {median:<8.1f}")

    def close_connection(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed")

    def process_samples(self, sample_names: List[str] = None,
                        add_differential: bool = True,
                        protein_coding_only: bool = False,
                        force_reload: bool = False):
        """
        Main method to process samples and generate synthetic data.

        Args:
            sample_names: List of sample names to process
            add_differential: Whether to add differential expression patterns
            protein_coding_only: If True, only generate data for protein coding genes
            force_reload: If True, force table deletion and recreate synthetic data
        """
        gene_filter = "protein coding" if protein_coding_only else "all"
        logger.info(f"Starting synthetic transcriptomics data generation for {gene_filter} genes...")

        # Connect to database
        self.connect_to_db()

        if force_reload:
            logger.info("Force reload requested - clearing existing data")
            self.cursor.execute("DROP TABLE IF EXISTS gene_expression")
            self.connection.commit()
            logger.info("Existing gene expression table dropped")

        # Create table and indexes
        self.create_expression_table()

        # Generate synthetic data
        expression_data = self.generate_synthetic_data(sample_names, add_differential, protein_coding_only)

        # Insert data
        self.insert_expression_data(expression_data)

        # Create indices after data insertion for optimal performance
        self.create_expression_indices()

        # Generate summary
        self.generate_expression_summary(sample_names)

        # Close connection
        self.close_connection()

def main():
    parser = argparse.ArgumentParser(description='Generate synthetic transcriptomics data')
    parser.add_argument('-l', '--host', default='localhost', help='Database host')
    parser.add_argument('-d', '--database', required=True, help='Database name')
    parser.add_argument('-u', '--user', required=True, help='Database user')
    parser.add_argument('-p', '--password', required=True, help='Database password')
    parser.add_argument('--port', default='5432', help='Database port')
    parser.add_argument('--samples', nargs='+', help='Sample names to generate data for (if not provided, uses all samples)')
    parser.add_argument('--no-differential', action='store_true', help='Skip adding differential expression patterns')
    parser.add_argument('--protein-coding-only', action='store_true', help='Generate data only for protein coding genes')
    parser.add_argument('--seed', type=int, help='Random seed for reproducible results')
    parser.add_argument('--force-reload', action='store_true', help='Clear existing data and regenerate transcriptomics data')

    args = parser.parse_args()

    # Set random seed for reproducibility
    if args.seed:
        np.random.seed(args.seed)
        random.seed(args.seed)
        logger.info(f"Random seed set to: {args.seed}")

    # Database configuration
    db_config = {
        'host': args.host,
        'database': args.database,
        'user': args.user,
        'password': args.password,
        'port': args.port
    }

    # Create generator instance and process samples
    generator = SyntheticTranscriptomicsGenerator(db_config)

    try:
        generator.process_samples(
            sample_names=args.samples,
            add_differential=not args.no_differential,
            protein_coding_only=args.protein_coding_only,
            force_reload=args.force_reload
        )
        logger.info("Synthetic transcriptomics data generation completed successfully!")

    except Exception as e:
        logger.error(f"Failed to generate synthetic data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()