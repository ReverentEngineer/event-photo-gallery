from setuptools import setup, find_packages

setup(
    name="event-phost-gallery",
    version='0.1.0',
    platforms="all",
    packages=find_packages(),
    package_data={
        "": ["*.html", "*.css"]
    },
    author="Jeff Caffrey-Hill",
    author_email="jeff@reverentengineer.com",
    install_requires=(
        'Flask',
        'Flask-SQLAlchemy',
        'Flask-Login',
        'pillow',
        'piexif',
    ),
)
