#!/usr/bin/env python3
import os
print('cwd:', os.getcwd())
print('abspath __file__:', os.path.abspath(__file__))
print('dirname:', os.path.dirname(os.path.abspath(__file__)))
print('src_dir:', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
print('src exists:', os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')))
print('src/__init__.py exists:', os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', '__init__.py')))
