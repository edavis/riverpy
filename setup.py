from setuptools import setup, find_packages

setup(
    name = 'riverpy',
    version = '0.1',
    packages = find_packages(),
    entry_points = {
        'console_scripts': [
            'river = riverpy:main',
        ],
    },
    install_requires = [
        'arrow==0.4.2',
        'bleach==1.2.2',
        'boto==2.21.0',
        'feedparser==5.1.3',
        'html5lib==0.95',
        'lxml==3.2.4',
        'python-dateutil==2.2',
        'redis==2.8.0',
        'requests==2.1.0',
        'six==1.4.1',
    ],
)
