#!/usr/bin/env python

from os import sep
from sys import path, argv
import sys
import string

gen_file = open("rose_opencl_code_opencl.cpp", 'r');
gen_lines = gen_file.readlines();

lines_host_file = [];
lines_kernel_file = [];

def isIfStatement(line):
  return (string.find(line, 'if(') != -1 or string.find(line, 'if (') != -1);

def isForLoopStatement(line):
  return string.find(line,'for(') != -1 or string.find(line,'for (') != -1;

def isOpParLoopStatement(line):
  return (string.find(line,'op_par_loop(') != -1 or string.find(line,'op_par_loop (') != -1);

def isEndOfStatement(line):
  return (string.find(line,'}') != -1);

def isBeginningOfStatement(line):
  return (string.find(line,'{') != -1);

def isKernelMethod(line):
  return (string.find(line, '__kernel') != -1);

def isIncludeStatement(line):
  return (string.find(line, '#include') != -1 or string.find(line, '# include') != -1); 

def isIfDefStatement(line):
  return (string.find(line, '#ifdef') != -1 or string.find(line, '# ifdef') != -1);

def isEndIfDefStatement(line):
  return (string.find(line, '#endif') != -1 or string.find(line, '# endif') != -1);
  
def isHostMethod(line):
  return (string.find(line, '_host') != -1);

def isInlineVoidMethod(line):
  return (string.find(line, 'inline void') != -1);

def isExternStatement(line):
  return (string.find(line, 'extern ') != -1);  

def isHashDefStatement(line):
  return (string.find(line, '#define') != -1 or string.find(line, '# define') != -1);

def addToCFInfo(statementName, statementDepth, CFInfoRootNode):
  currentDepth = 1;
  currentNode = CFInfoRootNode;
  while (currentDepth < statementDepth and len(currentNode['children']) > 0):
    currentNode = currentNode['children'][len(currentNode['children'])-1];
    currentDepth = currentDepth + 1;

  CFInfoNode = {
                  'name' : statementName,
                  'children' : [],
                  'depth' : statementDepth
              }
  currentNode['children'].append(CFInfoNode);
  return CFInfoRootNode;

def getCFInfoNode(nodeName, CFInfoRootNode):
  currentNode = CFInfoRootNode;
  if currentNode['name'] == nodeName:
    return currentNode;
  else:
    desiredNode = None;
    for node in currentNode['children']:
      desiredNode = getCFInfoNode(nodeName, node);
      if desiredNode != None and desiredNode['name'] == nodeName:
        return desiredNode;

def getParentCFInfoNode(nodeName, CFInfoRootNode):
  currentNode = CFInfoRootNode;
  for node in currentNode['children']:
    if node['name'] == nodeName:
      return currentNode;
  desiredNode = None;
  for node in currentNode['children']:
    desiredNode = getParentCFInfoNode(nodeName, node);
    if desiredNode != None:
      for node in desiredNode['children']:
        if node['name'] == nodeName:
          return desiredNode;

def addLinesToFileAndRemoveFromList(file_lines, gen_lines):
  openCurlyBraces = 0;
  closedCurlyBraces = 0;
  line_index = gen_lines.index(line);
  initial_line = line_index;
  while not isBeginningOfStatement(gen_lines[line_index]):
    line_index += 1;
  openCurlyBraces = 1;
  if isEndOfStatement(gen_lines[line_index]):
    closedCurlyBraces += 1;
  line_index += 1;
  while openCurlyBraces != closedCurlyBraces: 
    if isBeginningOfStatement(gen_lines[line_index]):
      openCurlyBraces += 1;
    if isEndOfStatement(gen_lines[line_index]):
      closedCurlyBraces += 1;
    line_index += 1;
  final_line = line_index;
  while final_line-initial_line > 0:
    file_lines.append(gen_lines[initial_line]);
    gen_lines.remove(gen_lines[initial_line]);
    final_line -= 1;
  return [file_lines, gen_lines];

openCurlyBraces = 0;
closedCurlyBraces = 0;

nestingLevel = 1;
index = 0;

for line in gen_lines:
  if isIfDefStatement(line):
    initial_line = gen_lines.index(line);
    line_index = initial_line;
    while not isEndIfDefStatement(line):
      line_index += 1;
    while line_index - initial_line > 1:
      lines_host_file.append(gen_lines[initial_line]);
      gen_lines.remove(gen_lines[initial_line]);
      line_index -= 1;
    lines_host_file.append(gen_lines[initial_line]);
  if isHashDefStatement(line):
    if string.find(line, 'ROUND_UP') != -1 or string.find(line, 'MIN') != -1 or string.find(line, 'ZERO_float') != -1:
      lines_kernel_file.append(line);
  if isIncludeStatement(line):
    lines_host_file.append(line);
  if isExternStatement(line):
    lines_host_file.append(line);
  if isInlineVoidMethod(line):
    [lines_kernel_file, gen_lines] = addLinesToFileAndRemoveFromList(lines_kernel_file, gen_lines);
  if isKernelMethod(line):
    [lines_kernel_file, gen_lines] = addLinesToFileAndRemoveFromList(lines_kernel_file, gen_lines); 
  if isHostMethod(line):
    [lines_host_file, gen_lines] = addLinesToFileAndRemoveFromList(lines_host_file, gen_lines); 


hosts_file = open('t_hosts.cpp','w');
kernels_file = open('t_kernels.cl','w');

hosts_file.writelines(lines_host_file);

kernels_file.writelines(lines_kernel_file);

print gen_lines;
