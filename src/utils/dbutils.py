# ---------------------------------------------------------------------------------------
# Application to read a one sample or multi-sample VCF file and save it to a postgres DB
#
# Author: Donald Friggieri
# email: dfriggieri@gmail.com
# ---------------------------------------------------------------------------------------
import psycopg2


def create_database(dbname, user, password, host):
    print("Creating database...")
    conn = psycopg2.connect(dbname='postgres', user=user, password=password, host=host)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS " + dbname)
    cur.execute("CREATE DATABASE " + dbname)
    cur.close()
    conn.close()


def create_tables(csq_fields, dbname, user, password, host):
    print("Creating tables...")
    conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE samples (
            id SERIAL PRIMARY KEY,
            sample_name VARCHAR(255) UNIQUE NOT NULL,
            sample_grp INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE variants_partitioned (
            id SERIAL,
            chromosome VARCHAR(25) NOT NULL,
            position INTEGER NOT NULL,
            ref TEXT NOT NULL,
            quality FLOAT,
            filter VARCHAR(255),
            PRIMARY KEY (chromosome, position, id)
        ) PARTITION BY RANGE (chromosome, position)
    """)

    for chromosome in range(1, 23):
        cur.execute(f"""
            CREATE TABLE variants_chr{chromosome} PARTITION OF variants_partitioned
            FOR VALUES FROM ('chr{chromosome}', 0) TO ('chr{chromosome}', 250000000)
        """)

    cur.execute("""
        CREATE TABLE variants_chrX PARTITION OF variants_partitioned
        FOR VALUES FROM ('chrX', 0) TO ('chrX', 250000000)
    """)

    cur.execute("""
        CREATE TABLE variants_chrY PARTITION OF variants_partitioned
        FOR VALUES FROM ('chrY', 0) TO ('chrY', 250000000)
    """)

    cur.execute("""
        CREATE TABLE variants_chrM PARTITION OF variants_partitioned
        FOR VALUES FROM ('chrM', 0) TO ('chrM', 25000)
    """)

    # Create a default partition for all other non-standard named chromosomes
    cur.execute("""
        CREATE TABLE variants_default PARTITION OF variants_partitioned DEFAULT
    """)

    cur.execute("""
        CREATE TABLE alts (
            id SERIAL PRIMARY KEY,
            variant_chromosome VARCHAR(25) NOT NULL,
            variant_position INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            alt TEXT NOT NULL,
            FOREIGN KEY (variant_chromosome, variant_position, variant_id) REFERENCES variants_partitioned (chromosome, position, id) ON DELETE CASCADE
        )
    """)

    annotation_columns = ", ".join([f"{field} TEXT" for field in csq_fields])
    cur.execute(f"""
        CREATE TABLE annotations (
            id SERIAL PRIMARY KEY,
            {annotation_columns}
        )
    """)

    cur.execute("""
        CREATE TABLE variant_annotations (
            id SERIAL PRIMARY KEY,
            alt_id INTEGER NOT NULL,
            annotation_id INTEGER NOT NULL,
            FOREIGN KEY (alt_id) REFERENCES alts (id) ON DELETE CASCADE,
            FOREIGN KEY (annotation_id) REFERENCES annotations (id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE genotypes (
            id SERIAL PRIMARY KEY,
            alt_id INTEGER NOT NULL,
            sample_id INTEGER NOT NULL,
            genotype VARCHAR(255),
            genotype_hr VARCHAR(255),
            is_phased BOOLEAN NOT NULL,
            dp INTEGER,
            gq INTEGER,
            ad JSONB,
            pl JSONB,
            FOREIGN KEY (alt_id) REFERENCES alts (id) ON DELETE CASCADE,
            FOREIGN KEY (sample_id) REFERENCES samples (id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE sample_relationships (
            id SERIAL PRIMARY KEY,
            sample_id1 INTEGER NOT NULL,
            sample_id2 INTEGER NOT NULL,
            relationship VARCHAR(255) NOT NULL,
            FOREIGN KEY (sample_id1) REFERENCES samples (id) ON DELETE CASCADE,
            FOREIGN KEY (sample_id2) REFERENCES samples (id) ON DELETE CASCADE,
            UNIQUE(sample_id1, sample_id2)
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


def create_sample(cur, sample_name):
    cur.execute("INSERT INTO samples (sample_name) VALUES (%s) RETURNING id", (sample_name,))
    return cur.fetchone()[0]
