from setuptools import setup, find_packages

setup(
    name = 'riverpy',
    version = '0.1',
    packages = find_packages(),
    author = 'Eric Davis',
    author_email = 'eric@davising.com',
    url = 'https://github.com/edavis/riverpy',
    entry_points = {
        'console_scripts': [
            'river = riverpy:main',
            'river-init = riverpy:river_init',
            'river-cleanup = riverpy:river_cleanup',
        ],
    },
    install_requires = [
        'Jinja2==2.7.1',
        'PyYAML==3.10',
        'arrow==0.4.2',
        'bleach==1.2.2',
        'boto==2.21.0',
        'feedparser==5.1.3',
        'html5lib==0.95',
        'lxml==3.2.4',
        'path.py==5.0',
        'python-dateutil==2.2',
        'redis==2.8.0',
        'requests==2.1.0',
        'six==1.4.1',
    ],
    package_data = {
        'riverpy': [
            'assets/apple-touch-icon-precomposed.png',
            'assets/favicon.ico',
            'assets/css/*',
            'assets/images/*',
            'assets/js/*',
            'templates/*.html',
        ],
    },
)
