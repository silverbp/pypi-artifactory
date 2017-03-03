#### Build Notes

python setup.py sdist bdist_wheel
twine upload dist/*

#### local dev

pip install -e ~/code/silverbp/pypi-artifactory --no-use-wheel