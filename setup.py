
import os
from setuptools import setup, find_packages
import subprocess


MAJOR_VERSION = '1'


version_file = os.path.join(os.path.dirname(__file__), 'pydc_control/VERSION')
if os.path.exists(version_file):
    # Read version from file
    with open(version_file, 'r', encoding='utf8') as fobj:
        version = fobj.read().strip()
else:
    # Generate the version and store it in the file
    result = subprocess.run('git rev-list --count HEAD', shell=True, capture_output=True, encoding='utf8')
    commit_count = result.stdout.strip()
    version = f'{MAJOR_VERSION}.{commit_count}'
    print(f'Setting version to {version} and writing to {version_file}')
    with open(version_file, 'w', encoding='utf8') as fobj:
        fobj.write(version)

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as fobj:
    long_description = fobj.read().strip()

setup(
    name='pydc-control',
    version=version,
    license='MIT',
    description='Used to control multiple docker compose projects in a coordinated way.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Adobe',
    author_email='noreply@adobe.com',
    url='https://github.com/adobe/pydc-control',
    platforms=['Any'],
    packages=find_packages(exclude=('*test*',)),
    install_requires=(
        'Jinja2>=2.7.2',
        'PyYAML>=5.1.2',
        'requests>=2',
    ),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],

)
