#### Build Notes

python setup.py sdist bdist_wheel

#### local dev

pip install -e ~/code/silverbp/pypi-artifactory --no-use-wheel
twine upload dist/*