#!/usr/bin/env python

from __future__ import division
from os import sep
from sys import path, argv
import sys
import string
import pycparser
import math
import copy
#import ~/Downloads/pycparser-2.06/pycparser/c_parser.py

#import inspect
#for name, obj in inspect.getmembers(pycparser):
#  if inspect.isclass(obj):
#    print obj

# helper methods & classes
def set_default_global_tuner():
  global_tuner = {'block_size' : 128,
                  'part_size' : 128,
                  'cache_line_size' : 128,
                  'op_warpsize' : 1,
                  'architecture' : Arch.ANY,
                  'name' : 'global_tuner',
                  'loop_tuner' : 0,
                  'active' : 1,
                  'fusion' : 1,
                  'loop_rotation' : 1,
                  'default' : 1,
                   'var_name' : None
                  }
  return global_tuner

class Arch:
  ANY = 0 
  CPU = 1
  GPU = 2
  ACCELERATOR = 3

# variables we need to keep track of
global_tuner = None;
loop_tuners = [];
op_par_loops = [];
default_arch = Arch.CPU;
default_file = 'airfoil.cpp';

#possible param values
possible_values_blk_part_size = [4, 8, 16, 32, 64, 128, 256, 512];  

# reading user input 
if len(sys.argv) > 1:
  if sys.argv[1] == "CPU":
    default_arch = Arch.CPU;
  else: 
    if sys.argv[1] == "GPU":
      default_arch = Arch.GPU;
    else: 
      if sys.argv[1] == "ACCELERATOR":
        default_arch = Arch.ACCELERATOR;
      else: 
        default_arch = Arch.ANY;
  if len(sys.argv) > 2:
    default_file = sys.argv[2];

# parsing the airfoil file
airfoil_file = open(default_file,'r');
lines = airfoil_file.readlines();

found = 0;
for line in lines:
  if "op_tuner" in line:
    found = 1;

#remove all useless lines
new_lines = [];
for line in lines:
  if not ("#include" or "#define") in line:
    new_lines.append(line);

if found:
    # the user has declared tuners

    global_tuner = set_default_global_tuner();

    # looking for op_tuner declarations
    for line in new_lines:
      if "op_tuner" in line:
        global_tuner_decl = 0;
        if ";" in line:
          # we found a 1 line declaration
          comps = line.split();
          
          #filtering the components
          temp_comps = [];
          for comp in comps:
            insert = 1;
            if "op_tuner" in comp:
              insert = insert and 0;
            if "=" in comp:
              insert = insert and 0;
              if len(comp) > 1:
                #perform split
                split_string.split('=');
            else:
              insert = insert and 1;
            if "op_create_global_tuner" in comp:
              global_tuner_decl = 1;
              insert = insert and 0;
            if insert == 1:
              temp_comps.append(comp);    
    
          # at this point, the temp_comps should only contain the variable name
          if global_tuner_decl:
            global_tuner['default'] = 0;
            global_tuner['var_name'] = temp_comps.pop();
          else:
            temp = temp_comps.pop();
            temp = temp.split("(");
            temp = temp.pop().split(")");
            temp = temp.pop(0).split("\"");
            temp = temp.pop(1);
            loop_tuners.append({ 'loop_tuner' : 1,
                                 'active' : 0,
                                 'var_name' : temp_comps.pop(0),
                                 'block_size' : 128,
                                 'part_size' : 128,
                                 'cache_line_size' : 128,
                                 'op_warpsize' : 128,
                                 'architecture' : Arch.ANY,
                                 'name' : temp,
                                 'fusion' : 0,
                                 'loop_rotation' : 1
                              });
        else:
          # declaration of op_tuner is over multiple lines
          print 'hello' 

        #print line;
    
      if not (global_tuner['var_name'] == None) and global_tuner['var_name'] in line:
        if not "op_tuner" in line:
          #else we've dealt with the case already above
          comp = line.split();
          var_name = comp.pop(0);
          if "=" in var_name:
            #this means that they did not use spaces
            var_name = var_name.split("=").pop(0);
          if "->" in var_name:
            var_name_comps = var_name.split("->");
          else:
            # this means they're using (*name).field notation
            var_name = var_name.replace('(','');
            var_name = var_name.replace(')','');
            var_name = var_name.replace('*','');  
            var_name_comps = var_name.split(".");
         
          # now var_name_comps.index(1) should contain the name of the field we're accessing. now we just need to retrieve the value it's assigned.
          global_tuner[var_name_comps.pop()] = comp.pop();
    
      # now doing the same for the loop tuners
      for loop_tuner in loop_tuners:
        if loop_tuner['var_name'] in line and not "op_tuner" and "=" in line:  
          comp = line.split();
          var_name = comp.pop(0);
          if "=" in var_name:
            var_name = var_name.split("=").pop(0);
          if "->" in var_name:
            var_name_comps = var_name.split("->");
          else:
            var_name = var_name.replace('(','');
            var_name = var_name.replace(')','');
            var_name = var_name.replace('*','');  
            var_name_comps = var_name.split(".");  
          loop_tuner[var_name_comps.pop()] = comp.pop(); 

else:
    # assume defaults
    global_tuner = set_default_global_tuner();
    
# looking for op_par_loop declarations
op_par_loop_relevant_lines = [];
current_loop = 0;

for line in new_lines:
  if "op_par_loop" in line:
    if ";" in line:
      # we have a 1 line op_par_loop - unlikely
      print line;
    else:
      # extract all relevant lines
      op_par_loop_relevant_lines.append([]);
      for line_index in range(new_lines.index(line), len(new_lines)):
        op_par_loop_relevant_lines[current_loop].append(new_lines[line_index]);
        if ";" in new_lines[line_index]:
          current_loop = current_loop + 1;
          break;

loopIndex = -1;
for loop in op_par_loop_relevant_lines:
  for comp in loop:
    comp = comp.strip();
    comp = comp.replace(' ', '');
    if "op_par_loop" in comp:
      temp_comp = comp.split("op_par_loop(");
      temp_comp = temp_comp.pop();
      temp_comp = temp_comp.split(",");
      temp_comp[1] = temp_comp[1].replace("\"", '');
      loop_name = temp_comp.pop(0);
      found = 0;
      for checkLoop in op_par_loops:
        if checkLoop['loop_name'] == loop_name:
          found = 1;
      if not found:
        op_par_loops.append({ 'loop_name' : loop_name,
                              'kernel_name' : temp_comp.pop(0),
                              'array' : temp_comp.pop(0),
                              'op_arg_dat' : [],
                              'op_arg_gbl' : [],
                              'tuner' : []
                            });
        loopIndex += 1;
      else:
        temp_comp.pop(0);
        temp_comp.pop(0);
    elif "op_arg_dat" in comp:
      temp_comp = comp.split("op_arg_dat(");
      temp_comp = temp_comp.pop();
      temp_comp = temp_comp.split(",");
      temp_comp[5] = temp_comp[5].replace(')','');
      temp_comp[5] = temp_comp[5].replace(';','');
      new_op_arg_dat = { 'name' : temp_comp.pop(0),
                         'access' : temp_comp.pop(0),
                         'indir_array' : temp_comp.pop(0),
                         'indir_array_access' : temp_comp.pop(0),
                         'type' : temp_comp.pop(0),
                         'operation_type' : temp_comp.pop(0)
                       };
      found = 0;
      #for arg in op_par_loops[op_par_loop_relevant_lines.index(loop)]['op_arg_dat']:
      for arg in op_par_loops[loopIndex]['op_arg_dat']:
        if arg == new_op_arg_dat:
          found = 1;
      if not found:
        #op_par_loops[op_par_loop_relevant_lines.index(loop)]['op_arg_dat'].append(new_op_arg_dat);
        op_par_loops[loopIndex]['op_arg_dat'].append(new_op_arg_dat);
    elif "op_arg_gbl" in comp:
      temp_comp = comp.split("op_arg_gbl(");
      temp_comp = temp_comp.pop();
      temp_comp = temp_comp.split(",");
      temp_comp[3] = temp_comp[3].replace(')','');
      temp_comp[3] = temp_comp[3].replace(';','');  
      temp_comp[0] = temp_comp[0].replace('&','');
      new_op_arg_gbl = { 'name' : temp_comp.pop(0),
                         'dimension' : temp_comp.pop(0),
                         'type' : temp_comp.pop(0),
                         'operation_type' : temp_comp.pop(0)
                       };
      found = 0;
      #for gbl_arg in op_par_loops[op_par_loop_relevant_lines.index(loop)]['op_arg_gbl']:
      for gbl_arg in op_par_loops[loopIndex]['op_arg_gbl']:
        if gbl_arg == new_op_arg_gbl:
          found = 1;
      if not found:
        op_par_loops[loopIndex]['op_arg_gbl'].append(new_op_arg_gbl);
        #op_par_loops[op_par_loop_relevant_lines.index(loop)]['op_arg_gbl'].append(new_op_arg_gbl);
    else:
      # this is the tuner argument
      temp_comp = comp;
      temp_comp = temp_comp.replace(');','');
      found = 0;
      #for tuner in op_par_loops[op_par_loop_relevant_lines.index(loop)]['tuner']:
      for tuner in op_par_loops[loopIndex]['tuner']:
        if tuner['name'] == temp_comp:
          found = 1;
      if not found:
        #op_par_loops[op_par_loop_relevant_lines.index(loop)]['tuner'].append({  'name' : temp_comp
        #                                                                   });
        op_par_loops[loopIndex]['tuner'].append({'name' : temp_comp });

#activate appropriate tuners
for loop_tuner in loop_tuners:
  for loop in op_par_loops:
    if loop_tuner['var_name'] == loop['tuner'][0]['name']:
      loop_tuner['active'] = 1;
# now we need to decide if we have any fusable loops
# we perform basic control flow

# helper functions

def getOriginalLoopName(loopTag, loopNameMap):
  for loop in loopNameMap:
    if loop['tag'] == loopTag:
      return loop['original'];

def isIfStatement(line):
  return ('if(' or 'if (' in line);

def isForLoopStatement(line):
  return string.find(line,'for(') != -1 or string.find(line,'for (') != -1;
  
def isOpParLoopStatement(line):
  return (string.find(line,'op_par_loop(') != -1 or string.find(line,'op_par_loop (') != -1);

def isEndOfStatement(line):
  return (string.find(line,'}') != -1);

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

core_lines = [];
found = False;

for line in new_lines:
  if string.find(line, 'op_init') != -1:
    found = True;
  if found:
    core_lines.append(line);

#CFInfo
CFInfoRootNode = {  'name' : 'ROOT',
                    'children' : [],
                    'depth' : 0
                 }
nestingLevel = 1;
orderOfAddition = [];
opParLoopNameMap = [];
index = 0;
indexOpParLoops = 0;
for line in core_lines:
  if isForLoopStatement(line):
    new_name = "for" + str(index);
    index = index + 1;
    CFInfoRootNode = addToCFInfo(new_name, nestingLevel, CFInfoRootNode);
    nestingLevel = nestingLevel + 1;
    orderOfAddition.append(new_name);
  else:
    if isOpParLoopStatement(line):
      line_comp = line.split('(');
      line_comp = line_comp[1];
      line_comp = line_comp.split(',');
      new_name='';
      for comp in line_comp:
        if '"' in comp:
          comp = comp.strip('"');
          new_name = comp;
      opParLoopNameMap.append({'original' : new_name, 'tag' : new_name + str(indexOpParLoops)});
      new_name += str(indexOpParLoops);
      CFInfoRootNode = addToCFInfo(new_name, nestingLevel, CFInfoRootNode);
      orderOfAddition.append(new_name);
      indexOpParLoops += 1;
    else:
      if isEndOfStatement(line) and len(CFInfoRootNode['children']) > 0:
        nestingLevel = nestingLevel - 1;
        
#print CFInfoRootNode;

def getOriginalOpParLoopName(loopTag):
  return getOriginalLoopName(loopTag, opParLoopNameMap);

# now we have the Control Flow Information so we can decide which loops we can fuse
# - 2 options: try all OR just go by nesting level. 
# Can fuse if they are in the same nesting level AND are next to each other.

# extract loop order

loops_in_order = [];

for loop in orderOfAddition:
  if (string.find(loop, 'for') == -1):
    loops_in_order.append(loop);

loops_in_order.append(loops_in_order[0]);
#print loops_in_order;
fusable_pairs = [];

for index in range(len(loops_in_order)-1):
  loop1 = getCFInfoNode(loops_in_order[index], CFInfoRootNode);
  depthLoop1 = loop1['depth'];
  loop2 = getCFInfoNode(loops_in_order[index+1], CFInfoRootNode);
  depthLoop2 = loop2['depth'];
  if depthLoop1 == depthLoop2:
    # need to check if there are any other statements in between
    parentNode = getParentCFInfoNode(loops_in_order[index], CFInfoRootNode);
    childrenNodes = parentNode['children'];
    child1Index = childrenNodes.index(loop1);
    child2Index = childrenNodes.index(loop2);
    if child1Index + 1 == child2Index:  
      #pair's fusable - add to fusable_pairs list
      fusable_pair = {
                      'loop1' : loop1['name'],
                      'loop2' : loop2['name']
                     }
      fusable_pairs.append(fusable_pair);
#print fusable_pairs;
#print loops_in_order;
#print op_par_loops;

#revert naming of fusable loops to original
tagged_fusable_pairs = copy.deepcopy(fusable_pairs);
fusable_pairs = [];

for pair in tagged_fusable_pairs:
  fusable_pairs.append({'loop1' : getOriginalOpParLoopName(pair['loop1']),
                        'loop2' : getOriginalOpParLoopName(pair['loop2'])});


#print fusable_pairs;
# we now do parmeter analysis to see if we can/should really fuse them
# let's leave this for the machine learning -> it is machine learning stuff

# define CBR

CBRCase = {
          'arch' : Arch.ANY,
          'fusable_pairs' : [], 
          'op_par_loops' : []     
          }
CBRSolution = {
              'loops_to_fuse' : [],
#              'final_loops' : [],
              'op_warpsize' : [],
              'block_size' : [],
              'part_size' : []
              }
CBRSystemCase = {
                'case' : None,
                'solution' : None,
                'occurances' : None
                }

CBRSystem = []

# case base:
  
CBRCase1 =  { 
            'arch' : Arch.CPU,
            'fusable_pairs' : [{'loop2': 'res_calc', 'loop1': 'adt_calc'}, {'loop2': 'bres_calc', 'loop1': 'res_calc'}, {'loop2': 'update', 'loop1': 'bres_calc'}],
            'op_par_loops' : [{'loop_name': 'save_soln', 'op_arg_dat': [{'indir_array': 'OP_ID', 'name': 'p_q', 'indir_array_access': '4', 'access': '-1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'OP_ID', 'name': 'p_qold', 'indir_array_access': '4', 'access': '-1', 'operation_type': 'OP_WRITE', 'type': 'REAL_STRING'}], 'op_arg_gbl': [], 'kernel_name': 'save_soln', 'tuner': [], 'array': 'cells'}, {'loop_name': 'adt_calc', 'op_arg_dat': [{'indir_array': 'pcell', 'name': 'p_x', 'indir_array_access': '2', 'access': '0', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pcell', 'name': 'p_x', 'indir_array_access': '2', 'access': '1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pcell', 'name': 'p_x', 'indir_array_access': '2', 'access': '2', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pcell', 'name': 'p_x', 'indir_array_access': '2', 'access': '3', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'OP_ID', 'name': 'p_q', 'indir_array_access': '4', 'access': '-1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'OP_ID', 'name': 'p_adt', 'indir_array_access': '1', 'access': '-1', 'operation_type': 'OP_WRITE', 'type': 'REAL_STRING'}], 'op_arg_gbl': [], 'kernel_name': 'adt_calc', 'tuner': [], 'array': 'cells'}, {'loop_name': 'res_calc', 'op_arg_dat': [{'indir_array': 'pedge', 'name': 'p_x', 'indir_array_access': '2', 'access': '0', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pedge', 'name': 'p_x', 'indir_array_access': '2', 'access': '1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pecell', 'name': 'p_q', 'indir_array_access': '4', 'access': '0', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pecell', 'name': 'p_q', 'indir_array_access': '4', 'access': '1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pecell', 'name': 'p_adt', 'indir_array_access': '1', 'access': '0', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pecell', 'name': 'p_adt', 'indir_array_access': '1', 'access': '1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pecell', 'name': 'p_res', 'indir_array_access': '4', 'access': '0', 'operation_type': 'OP_INC', 'type': 'REAL_STRING'}, {'indir_array': 'pecell', 'name': 'p_res', 'indir_array_access': '4', 'access': '1', 'operation_type': 'OP_INC', 'type': 'REAL_STRING'}], 'op_arg_gbl': [], 'kernel_name': 'res_calc', 'tuner': [], 'array': 'edges'}, {'loop_name': 'bres_calc', 'op_arg_dat': [{'indir_array': 'pbedge', 'name': 'p_x', 'indir_array_access': '2', 'access': '0', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pbedge', 'name': 'p_x', 'indir_array_access': '2', 'access': '1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pbecell', 'name': 'p_q', 'indir_array_access': '4', 'access': '0', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pbecell', 'name': 'p_adt', 'indir_array_access': '1', 'access': '0', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'pbecell', 'name': 'p_res', 'indir_array_access': '4', 'access': '0', 'operation_type': 'OP_INC', 'type': 'REAL_STRING'}, {'indir_array': 'OP_ID', 'name': 'p_bound', 'indir_array_access': '1', 'access': '-1', 'operation_type': 'OP_READ', 'type': '"int"'}], 'op_arg_gbl': [], 'kernel_name': 'bres_calc', 'tuner': [], 'array': 'bedges'}, {'loop_name': 'update', 'op_arg_dat': [{'indir_array': 'OP_ID', 'name': 'p_qold', 'indir_array_access': '4', 'access': '-1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}, {'indir_array': 'OP_ID', 'name': 'p_q', 'indir_array_access': '4', 'access': '-1', 'operation_type': 'OP_WRITE', 'type': 'REAL_STRING'}, {'indir_array': 'OP_ID', 'name': 'p_res', 'indir_array_access': '4', 'access': '-1', 'operation_type': 'OP_RW', 'type': 'REAL_STRING'}, {'indir_array': 'OP_ID', 'name': 'p_adt', 'indir_array_access': '1', 'access': '-1', 'operation_type': 'OP_READ', 'type': 'REAL_STRING'}], 'op_arg_gbl': [{'operation_type': 'OP_INC', 'type': 'REAL_STRING', 'name': 'rms', 'dimension': '1'}], 'kernel_name': 'update', 'tuner': [], 'array': 'cells'}]
            }

CBRSolution1 =  {
                'loops_to_fuse' : [],
                'op_warpsize' : 1,
                'block_size' : 4,
                'part_size' : 4
                }

CBRCase2 = copy.deepcopy(CBRCase1);
CBRCase2['arch'] = Arch.GPU;

CBRSolution2 =  {
                'loops_to_fuse' : [],
                'op_warpsize' : 32,
                'block_size' : 256,
                'part_size' : 256
                }

CBRCase3 =  copy.deepcopy(CBRCase1);
CBRCase3['arch'] = Arch.ANY;

CBRSolution3 = copy.deepcopy(CBRSolution1);

CBRCase4 = copy.deepcopy(CBRCase1);
CBRCase4['arch'] = Arch.ACCELERATOR;

CBRSolution4 = copy.deepcopy(CBRSolution1);

trainingCases = [CBRCase1, CBRCase2, CBRCase1, CBRCase3, CBRCase4];
results = [CBRSolution1, CBRSolution2, CBRSolution1, CBRSolution3, CBRSolution4];

def retrieveTrainingData():
  return [trainingCases, results];

# init CBR

betterMatchFound = False;

def checkResult(solvedCase):
  #[correctlyIdentified, fusions, parms];
  return [True, [], None];  

def opArgDatMatch(opArgDat1, opArgDat2):
  return opArgDat1['indir_array'] == opArgDat2['indir_array'] and opArgDat1['access'] == opArgDat2['access'] and opArgDat1['name'] == opArgDat2['name'];

def opParLoopArrayMatch(opParLoop1, opParLoop2):
  return opParLoop1['array'] == opParLoop2['array'];

def checkExistsAndIncr(CBRSystemCase, CBRSystem):
  sysCase = retrieveSysCase(CBRSystemCase, CBRSystem);
  if sysCase != None: 
    sysCase['occurances'] = sysCase['occurances'] + 1;
  else:
    CBRSystem.append(CBRSystemCase);
  return CBRSystem;

def fullCaseEquals(case, CBRSystemCase):
  return case['case'] == CBRSystemCase['case'] and case['solution'] == CBRSystemCase['solution'];

def equals(case, CBRSystemCase):
  return case['case'] == CBRSystemCase['case'];

def createCase(CBRCase):
  newCase['case'] = CBRCase;
  newCase['solution'] = None;
  newCase['occurances'] = 1;
  return newCase;

def retrieveSysCase(CBRSystemCase, CBRSystem):
  for case in CBRSystem:
    if fullCaseEquals(case, CBRSystemCase):
      return case;  
  return None;

def caseLookup(CBRSystem, unmatchedCase):
  for case in CBRSystem:
    if equals(case, unmatchedCase):
      return case;
  return None;  

def checkComparable(CBRCase1, CBRCase2):
  return CBRCase1['op_par_loops'] == CBRCase2['op_par_loops'];

def getLoopInfo(loopName, op_par_loops):
  for loop in op_par_loops:
    if loop['loop_name'] == loopName:
      return loop;
  return None;

def fusableLoopsWeighting(CBRCase):
  weighting = 0;
  for pair in CBRCase['fusable_pairs']:
    loop1 = getLoopInfo(pair['loop1'], CBRCase['op_par_loops']);
    loop2 = getLoopInfo(pair['loop2'], CBRCase['op_par_loops']);
    if opParLoopArrayMatch(loop1, loop2):
      weighting += 1;
  return weighting;

def opArgDatSameDataArray(opArgDat1, opArgDat2):
  return opArgDat1['name'] == opArgDat2['name'] and opArgDat1['indir_array'] == opArgDat2['indir_array'];

def calculateLoopFusionComplexity(loop1, loop2, arch):
  complexity = 0;
  noOfEqualArgs = 0;
  hasEqual = [0 for i in range (len(loop2['op_arg_dat']))];
  for dataArg1 in loop1['op_arg_dat']:
    for dataArg2 in loop2['op_arg_dat']:
      if opArgDatMatch(dataArg1, dataArg2):
        noOfEqualArgs += 1;
        hasEqual[loop2['op_arg_dat'].index(dataArg2)] +=  1;
  totalNoOfArgs = len(loop1['op_arg_dat']) + len(loop2['op_arg_dat']);
  propEqualArgsLoop1 = noOfEqualArgs/len(loop1['op_arg_dat']);
  propEqualArgsLoop2 = noOfEqualArgs/len(loop2['op_arg_dat']);
  matched = [0 for i in range(len(loop2['op_arg_dat']))];
  noOfSameDatAndArrayCases = 0;
  for dataArg1 in loop1['op_arg_dat']:
    for index in range(0,len(loop2['op_arg_dat'])):
      if not matched[index] and not opArgDatMatch(dataArg1, dataArg2) and not hasEqual[index]:
        if opArgDatSameDataArray(dataArg1, loop2['op_arg_dat'][index]):
          matched[index] += 1;
          noOfSameDatAndArrayCases += 1;
  propSimilarArgsLoop1 = noOfSameDatAndArrayCases/len(loop1['op_arg_dat']);
  propSimilarArgsLoop2 = noOfSameDatAndArrayCases/len(loop2['op_arg_dat']);
  propDiffArgsLoop1 = (len(loop1['op_arg_dat']) - (noOfEqualArgs + noOfSameDatAndArrayCases))/len(loop1['op_arg_dat']);
  propDiffArgsLoop2 = (len(loop2['op_arg_dat']) - (noOfEqualArgs + noOfSameDatAndArrayCases))/len(loop2['op_arg_dat']);
  if arch == Arch.CPU:
    sameArgsWeighting = 10;
    similarArgsWeighting = 5;
    differentArgsWeighting = -0.2;
    noOfArgsWeighting = -0.1;
  else: 
    sameArgsWeighting = 10;
    similarArgsWeighting = 5;
    differentArgsWeighting = -0.2;
    noOfArgsWeighting = -0.2;
  complexity += (propEqualArgsLoop1 + propEqualArgsLoop2) *sameArgsWeighting * noOfEqualArgs + (
                (propSimilarArgsLoop1 + propSimilarArgsLoop2) * similarArgsWeighting * noOfSameDatAndArrayCases) + ( 
                (propDiffArgsLoop1 + propDiffArgsLoop2) * differentArgsWeighting * (totalNoOfArgs - (noOfEqualArgs + noOfSameDatAndArrayCases))) + ( 
                totalNoOfArgs * noOfArgsWeighting);
  return complexity;
  
def opDatArgsWeighting(CBRCase):
  weighting = 0;
  availableLoops = [];
  for loop in CBRCase['op_par_loops']:
    availableLoops.append(loop['loop_name']);
  for pair in CBRCase['fusable_pairs']:
    loop1 = getLoopInfo(pair['loop1'], CBRCase['op_par_loops']);
    loop2 = getLoopInfo(pair['loop2'], CBRCase['op_par_loops']);
    if opParLoopArrayMatch(loop1, loop2):
      complexity = calculateLoopFusionComplexity(loop1, loop2, CBRCase['arch']);
      weighting += complexity;    
  return weighting;

def fusablePairsIntersection(fusablePairs1, fusablePairs2):
  intersectingFusablePairs = [];
  for pair1 in fusablePairs1:
    for pair2 in fusablePairs2:
      if pair1 == pair2:
        intersectingFusablePairs.append(pair1);
  return intersectingFusablePairs;

def opParLoopsIntersection(op_par_loops1, op_par_loops2):
  intersectingOpParLoops = [];
  for op_par_loop1 in op_par_loops1:
    for op_par_loop2 in op_par_loops2:
      if op_par_loop1 == op_par_loop2:
        intersectingOpParLoops.append(op_par_loop1);
  return intersectingOpParLoops;

def opArgDatComplexity(loop, arch):
  complexity = 0;
  dataSameArrayAccesses = [];
  for dataArg in loop['op_arg_dat']:
    found = False;
    for index in range(0, len(dataSameArrayAccesses)):
      if dataArg['name'] == dataSameArrayAccesses[index]['name'] and (
         dataArg['indir_array'] == dataSameArrayAccesses[index]['indir_array']):
        dataSameArrayAccesses[index]['occurances'] += 1;
        found = True;
    if not found: 
      dataArrayAccess = {
                        'name' : dataArg['name'],
                        'indir_array' : dataArg['indir_array'],
                        'occurances' : 1 
                        }
      dataSameArrayAccesses.append(dataArrayAccess);
  
  noOfDifferentDataArrayArgsComplexity = 1;
  if arch == Arch.GPU:
    noOfDifferentDataArrayArgsComplexity = 1.1;
  complexity +=  noOfDifferentDataArrayArgsComplexity * len(dataSameArrayAccesses);
  
  totalNoOfArgsComplexity = 0.25;
  if arch == Arch.GPU:
    totalNoOfArgsComplexity = 0.5; 
  complexity += len(loop['op_arg_dat']) * totalNoOfArgsComplexity;
  return complexity;

def similarityEstimation(CBRSystem, unmatchedCase):
  noOfProperties = 6; # 4 - 1 for each arch, 1 for fusable_loops, 1 for op_dats
  archWeight = 5;
  weightedProperties = [ [ 0 for i in range(noOfProperties) ] for j in range(len(CBRSystem)) ];
  for index in range(len(CBRSystem)):
    weightedProperties[index][CBRSystem[index]['case']['arch']] += archWeight * CBRSystem[index]['occurances'];
    weightedProperties[index][4] += fusableLoopsWeighting(CBRSystem[index]['case']) * CBRSystem[index]['occurances'];
    weightedProperties[index][5] += opDatArgsWeighting(CBRSystem[index]['case']) * CBRSystem[index]['occurances'];
  print weightedProperties; 

  # normalize results
  for index in range(len(CBRSystem)):
    for prop in range(noOfProperties):
      weightedProperties[index][prop] /= sum(weightedProperties[index]);

  print weightedProperties;
  # here calculate the weight of the intersection
    
  noOfIntersectingProperties = 3;
  weightedIntersection = [ [ 0 for i in range(noOfIntersectingProperties) ] for j in range(len(CBRSystem)) ];
  maxWeight = 0;
  maxIndex = 0;
  maxList = [];
  for index in range(len(CBRSystem)):
    if checkComparable(unmatchedCase['case'], CBRSystem[index]['case']):
      intersectingArch = Arch.ANY;
      if unmatchedCase['case']['arch'] == CBRSystem[index]['case']['arch']:
        weightedIntersection[index][0] += weightedProperties[index][CBRSystem[index]['case']['arch']];
        intersectingArch = unmatchedCase['case']['arch'];

      intersectingCase =  {
                          'arch' : intersectingArch,
                          'fusable_pairs': fusablePairsIntersection(CBRSystem[index]['case']['fusable_pairs'], unmatchedCase['case']['fusable_pairs']),
                          'op_par_loops': opParLoopsIntersection(CBRSystem[index]['case']['op_par_loops'], unmatchedCase['case']['op_par_loops'])
                          }
     
      weightedIntersection[index][1] += fusableLoopsWeighting(intersectingCase) * weightedProperties[index][4]; 
      weightedIntersection[index][2] += opDatArgsWeighting(intersectingCase) * weightedProperties[index][5];
      if sum(weightedIntersection[index]) > maxWeight:
        maxWeight = sum(weightedIntersection[index]);
        maxIndex = 0;
        maxList = [];
      if sum(weightedIntersection[index]) == maxWeight:
        maxIndex += 1;
        maxList.append(CBRSystem[index]);

    if maxIndex > 0:
      for index1 in range(maxIndex-1):
        for index2 in range(index1+1,maxIndex):
          if maxList[index1]['occurances'] < maxList[index2]['occurances']:
            aux = maxList[index1];
            maxList[index1] = maxList[index2];
            maxList[index2] = aux;   
 
  if len(maxList) > 0: 
    return maxList[0];
    
  return None;

def bestCaseMatch(CBRSystem, unmatchedCase):
  tempCase = caseLookup(CBRSystem, unmatchedCase);
  
  if tempCase == None or not equals(tempCase, unmatchedCase):
    tempCase = similarityEstimation(CBRSystem, unmatchedCase); 
 
  return tempCase;

def checkBestMatch(CBRSystem, newCase, bestMatch):
  maxComplexity = 0;
  loopFusionComplexity = [];
  wantedFusion = None;  
  for pair in newCase['case']['fusable_pairs']:
    loop1 = getLoopInfo(pair['loop1'], newCase['case']['op_par_loops']);
    loop2 = getLoopInfo(pair['loop2'], newCase['case']['op_par_loops']); 
    if opParLoopArrayMatch(loop1, loop2):
      complexity =  calculateLoopFusionComplexity(loop1, loop2, CBRCase['arch'])
      fusionComplexity =  {
                          'fusion' : pair,
                          'complexity' : complexity
                          }
      loopFusionComplexity.append(fusionComplexity);
      if complexity > maxComplexity:
        maxComplexity = complexity;

  threshold = 0;
  if maxComplexity > 0:
    # we have a good loop fusion
    # now we check if the bestMatch does it;
    wantedFusion = None;
    for fusion in loopFusionComplexity:
      if fusion['complexity'] == maxComplexity:
        wantedFusion = fusion['fusion'];
    print wantedFusion;
    if bestMatch != None and checkComparable(newCase['case'], bestMatch['case']):
      loopsToFuse = bestMatch['solution']['loops_to_fuse']; 
      if loopsToFuse.index(wantedFusion) != -1:
        return [True, bestMatch];
      else:
        if newCase['case']['arch'] == Arch.CPU and bestMatch['solution']['op_warpsize'] == 1:
          return [True, bestMatch];
  else:   
    # we have no loop fusions
    if bestMatch != None and checkComparable(newCase['case'], bestMatch['case']):
      if len(bestMatch['solution']['loops_to_fuse']) == 0: 
        return [True, bestMatch];
      else:
        if newCase['case']['arch'] == Arch.CPU and bestMatch['solution']['op_warpsize'] == 1:
          return [True, bestMatch];
  # else, we clearly have a better case, so we shall create a new best case
  
  op_warpsize = 1;
  if newCase['case']['arch'] == Arch.GPU:
    op_warpsize = 32;

  overallMaxComplexity = 0;
    
  for loop in newCase['case']['op_par_loops']:
    complexity = opArgDatComplexity(loop, newCase['case']['arch']);
    if complexity > overallMaxComplexity:
      overallMaxComplexity = complexity;

  if maxComplexity > overallMaxComplexity:
    overallMaxComplexity = maxComplexity;
 
  complexityThresholdForDiffValuePartBlkSize = 4;
  
  temp_block_size = 128;
  temp_part_size = 128;
  referenceValue = 256;
  adjustmentFactor = 16;
  if newCase['case']['arch'] == Arch.CPU:
    temp_block_size =  1/overallMaxComplexity * referenceValue * adjustmentFactor;
  else:
    temp_block_size = overallMaxComplexity/2 * referenceValue;

  diffArray = [];
  for val in possible_values_blk_part_size:
    diffArray.append(math.fabs(temp_block_size - val));
  minDiff = min(diffArray);
  for index in range(len(possible_values_blk_part_size)):
    if (diffArray[index] == minDiff):
      temp_block_size = possible_values_blk_part_size[index];
  if overallMaxComplexity >= complexityThresholdForDiffValuePartBlkSize or temp_block_size < 512:
    temp_part_size = temp_block_size;
  else:
    temp_part_size = 2 * temp_block_size; 
 
  newSolution = {
                'loops_to_fuse' : wantedFusion,
                'op_warpsize' : op_warpsize,
                'block_size' : temp_block_size, 
                'part_size' : temp_part_size
                }

  newBestMatch =  {
                  'case' : newCase['case'],
                  'solution' : newSolution,
                  'occurances' : 1
                  }
  return [False, newBestMatch]; 

def retrieve(CBRSystem, newCase):
  bestMatch =  bestCaseMatch(CBRSystem, newCase);

  # failsafe no 1 - we need to see if this is really a good option.
  # this situation might have not been encountered
  [betterMatchFound, betterMatch] = checkBestMatch(CBRSystem, newCase, bestMatch);
  return betterMatch;

def reuse(bestCase, newCase):
  newCase['solution'] = bestCase['solution'];
  return newCase;

def retain(CBRSystem, solvedCase):
  return checkExistsAndIncr(solvedCase, CBRSystem); 
 
def CBRInit(CBRSystem, trainingCases, results):
  for index in range(0, len(trainingCases)):
    CBRSystemCase = {
                    'case' : trainingCases[index],
                    'solution' : results[index], 
                    'occurances' : 1
                    };
    CBRSystem = checkExistsAndIncr(CBRSystemCase, CBRSystem);
  return CBRSystem;

# parsing the tuner_correctness file
totalCases = 0;
machineLearningCorrectness = 0;
tuner_correctness_file = open('tuner_correctness','r');
tc_lines = tuner_correctness_file.readlines();
for line in tc_lines:
  if string.find(line, 'total_cases:') != -1:
    comp = line.split(':');
    totalCases = int(comp[1].strip());
  elif string.find(line, 'correctly_classified:') != -1:
    comp = line.split(':');
    machineLearningCorrectness = int(comp[1].strip());
  else:
    print 'unidentified line';

[trainingCases, results] = retrieveTrainingData();
CBRSystem = CBRInit(CBRSystem, trainingCases, results);

# create vector of properties - the case

newCase = {
          'case' :  {
                    'arch' : default_arch,
                    'fusable_pairs' : fusable_pairs, 
                    'op_par_loops' : op_par_loops
                    },
          'solution' : None,
          'occurances' : 1
          }

# call machine learning to retrieve best result for the current case

bestCase = retrieve(CBRSystem, newCase);


solvedCase = reuse(bestCase, newCase);

print solvedCase['solution'];

totalCases = totalCases+1;
# we want to make sure that the ML algorithm has chosen the best option
# we also count the number of occurances of it being correct
[correctlyIdentified, fusions, params] = checkResult(solvedCase);
if correctlyIdentified:
  machineLearningCorrectness = machineLearningCorrectness + 1;
  CBRSystem = retain(CBRSystem, solvedCase);
else:
  adjustedCase['case'] = solvedCase['case'];
  adjustedCase['solution'] =  { 
                              'loops_to_fuse' : fusions,
                              'op_warpsize' : params['op_warpsize'],
                              'block_size' : params['block_size'],
                              'part_size' : params['part_size']
                              } 
  adjustedCase['occurances']= 1
  CBRSystem = retain(CBRSystem, adjustedCase);

#print correctlyIdentified;
#print solvedCase['solution'];
# store correctness results to file
tuner_correctness_file = open('tuner_correctness','w');
correctness_info = ['total_cases: ' + str(totalCases) + '\n', 'correctly_classified: ' + str(machineLearningCorrectness)]
tuner_correctness_file.writelines(correctness_info);

# transform the best case into compiler flags

# call compiler 



