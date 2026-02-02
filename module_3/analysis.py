"""Analysis queries on the applicant_data database."""

import psycopg

conn = psycopg.connect(dbname="applicant_data", user="dawnaproskourine", host="127.0.0.1")
cursor = conn.cursor()

# How many entries applied for Fall 2026?
cursor.execute("SELECT COUNT(*) FROM applicants WHERE term = 'Fall 2026'")
print(f"Fall 2026 applicants: {cursor.fetchone()[0]}")

# What percentage of entries are from international students?
cursor.execute("""
    SELECT ROUND(
        100.0 * COUNT(*) FILTER (WHERE us_or_international = 'International')
        / COUNT(*), 2
    ) FROM applicants
""")
print(f"International student percentage: {cursor.fetchone()[0]}%")

# Average GPA, GRE, GRE V, GRE AW of applicants who provided these metrics
cursor.execute("""
    SELECT
        ROUND(AVG(gpa)::numeric, 2),
        ROUND(AVG(gre)::numeric, 2),
        ROUND(AVG(gre_v)::numeric, 2),
        ROUND(AVG(gre_aw)::numeric, 2)
    FROM applicants
    WHERE gpa IS NOT NULL OR gre IS NOT NULL OR gre_v IS NOT NULL OR gre_aw IS NOT NULL
""")
row = cursor.fetchone()
print(f"Average GPA: {row[0]}")
print(f"Average GRE: {row[1]}")
print(f"Average GRE V: {row[2]}")
print(f"Average GRE AW: {row[3]}")

# Average GPA of American students in Fall 2026
cursor.execute("""
    SELECT ROUND(AVG(gpa)::numeric, 2)
    FROM applicants
    WHERE us_or_international = 'American'
      AND term = 'Fall 2026'
      AND gpa IS NOT NULL
""")
print(f"Average GPA of American students (Fall 2026): {cursor.fetchone()[0]}")

# What percentage of Fall 2026 entries are acceptances?
cursor.execute("""
    SELECT ROUND(
        100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
        / COUNT(*), 2
    ) FROM applicants
    WHERE term = 'Fall 2026'
""")
print(f"Fall 2026 acceptance percentage: {cursor.fetchone()[0]}%")

# Average GPA of accepted applicants in Fall 2026
cursor.execute("""
    SELECT ROUND(AVG(gpa)::numeric, 2)
    FROM applicants
    WHERE term = 'Fall 2026'
      AND status ILIKE 'Accepted%%'
      AND gpa IS NOT NULL
""")
print(f"Average GPA of accepted applicants (Fall 2026): {cursor.fetchone()[0]}")

# How many applied to JHU for a Masters in Computer Science?
cursor.execute("""
    SELECT COUNT(*)
    FROM applicants
    WHERE llm_generated_university ILIKE '%%Johns Hopkins%%'
      AND llm_generated_program ILIKE '%%Computer Science%%'
      AND degree = 'Masters'
""")
print(f"JHU Masters in Computer Science applicants: {cursor.fetchone()[0]}")

# How many 2026 acceptances for PhD in CS at Georgetown, MIT, Stanford, or CMU?
# Using program field
cursor.execute("""
    SELECT COUNT(*)
    FROM applicants
    WHERE term ILIKE '%%2026'
      AND status ILIKE 'Accepted%%'
      AND degree = 'PhD'
      AND program ILIKE '%%Computer Science%%'
      AND (program ILIKE '%%Georgetown University%%'
        OR program ILIKE '%%Massachusetts Institute of Technology%%'
        OR program ILIKE '%%Stanford University%%'
        OR program ILIKE '%%Carnegie Mellon University%%')
""")
print(f"2026 PhD CS acceptances (Georgetown, MIT, Stanford, CMU) [program]: {cursor.fetchone()[0]}")

# Same query using llm_generated fields
cursor.execute("""
    SELECT COUNT(*)
    FROM applicants
    WHERE term ILIKE '%%2026'
      AND status ILIKE 'Accepted%%'
      AND degree = 'PhD'
      AND llm_generated_program ILIKE '%%Computer Science%%'
      AND llm_generated_university IN (
          'Georgetown University',
          'Massachusetts Institute of Technology',
          'Stanford University',
          'Carnegie Mellon University'
      )
""")
print(f"2026 PhD CS acceptances (Georgetown, MIT, Stanford, CMU) [llm]: {cursor.fetchone()[0]}")

# Top 10 most popular programs
cursor.execute("""
    SELECT llm_generated_program, COUNT(*) AS num_applicants
    FROM applicants
    WHERE llm_generated_program IS NOT NULL AND llm_generated_program != ''
    GROUP BY llm_generated_program
    ORDER BY num_applicants DESC
    LIMIT 10
""")
print("\nTop 10 most popular programs:")
for i, (program, count) in enumerate(cursor.fetchall(), 1):
    print(f"  {i}. {program}: {count}")

# Top 10 most popular universities
cursor.execute("""
    SELECT llm_generated_university, COUNT(*) AS num_applicants
    FROM applicants
    WHERE llm_generated_university IS NOT NULL AND llm_generated_university != ''
    GROUP BY llm_generated_university
    ORDER BY num_applicants DESC
    LIMIT 10
""")
print("\nTop 10 most popular universities:")
for i, (university, count) in enumerate(cursor.fetchall(), 1):
    print(f"  {i}. {university}: {count}")

# Acceptance rate by degree type (PhD vs Masters)
cursor.execute("""
    SELECT
        degree,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%') AS accepted,
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
            / COUNT(*), 2
        ) AS acceptance_rate
    FROM applicants
    WHERE degree IN ('PhD', 'Masters')
    GROUP BY degree
    ORDER BY degree
""")
print("\nAcceptance rate by degree type:")
for degree, total, accepted, rate in cursor.fetchall():
    print(f"  {degree}: {accepted}/{total} ({rate}%)")

# International vs American acceptance rate
cursor.execute("""
    SELECT
        us_or_international,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%') AS accepted,
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE status ILIKE 'Accepted%%')
            / COUNT(*), 2
        ) AS acceptance_rate
    FROM applicants
    WHERE us_or_international IN ('American', 'International')
    GROUP BY us_or_international
    ORDER BY us_or_international
""")
print("\nAcceptance rate by nationality:")
for nationality, total, accepted, rate in cursor.fetchall():
    print(f"  {nationality}: {accepted}/{total} ({rate}%)")

conn.close()