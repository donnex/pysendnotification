from distutils.core import setup

setup(
    name='sendnotification',
    version='0.1',
    description='Send notification',
    url='',
    py_modules=['sendnotification'],
    scripts=['bin/sendnotification'],

    author='Daniel Johansson',
    author_email='donnex@donnex.net',
    license='BSD',

    install_requires=[
        'redis',
        'requests',
    ]
)
