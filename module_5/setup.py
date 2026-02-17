"""Package setup for module_5 — GradCafe Analysis Dashboard."""

from setuptools import setup, find_packages

setup(
    name="gradcafe-analysis",
    version="1.0.0",
    description="GradCafe applicant analysis dashboard",
    author="Dawna Jones Proskourine",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    py_modules=[
        "app",
        "query_data",
        "load_data",
        "cleanup_data",
        "scrape",
        "robots_checker",
    ],
    install_requires=[
        "Flask>=3.0",
        "psycopg>=3.0",
        "beautifulsoup4>=4.12",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "pylint>=3.0",
            "pydeps>=2.0",
        ],
    },
    package_data={
        "": [
            "canon_programs.txt",
            "canon_universities.txt",
            "llm_extended_applicant_data.json",
            "create_app_user.sql",
            "website/_templates/*.html",
            "website/_static/*.css",
            "website/_static/*.js",
        ],
    },
)
