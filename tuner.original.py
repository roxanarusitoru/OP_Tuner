#!/usr/bin/env python

from os import sep
from sys import path, argv
import string
import pycparser
#import ~/Downloads/pycparser-2.06/pycparser/c_parser.py

import inspect
for name, obj in inspect.getmembers(pycparser):
  if inspect.isclass(obj):
    print obj

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

# parsing the airfoil file
airfoil_file = open('airfoil.cpp','r');
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
  
for loop in op_par_loop_relevant_lines:
  for comp in loop:
    comp = comp.strip();
    comp = comp.replace(' ', '');
    if "op_par_loop" in comp:
      temp_comp = comp.split("op_par_loop(");
      temp_comp = temp_comp.pop();
      temp_comp = temp_comp.split(",");
      temp_comp[1] = temp_comp[1].replace("\"", '');
      op_par_loops.append({ 'loop_name' : temp_comp.pop(0),
                            'kernel_name' : temp_comp.pop(0),
                            'array' : temp_comp.pop(0),
                            'op_arg_dat' : [],
                            'op_arg_gbl' : [],
                            'tuner' : []
                          });
    elif "op_arg_dat" in comp:
      temp_comp = comp.split("op_arg_dat(");
      temp_comp = temp_comp.pop();
      temp_comp = temp_comp.split(",");
      temp_comp[5] = temp_comp[5].replace(')','');
      temp_comp[5] = temp_comp[5].replace(';','');
      op_par_loops[op_par_loop_relevant_lines.index(loop)]['op_arg_dat'].append({ 'name' : temp_comp.pop(0),
                                                                                  'access' : temp_comp.pop(0),
                                                                                  'indir_array' : temp_comp.pop(0),
                                                                                  'indir_array_access' : temp_comp.pop(0),
                                                                                  'type' : temp_comp.pop(0),
                                                                                  'operation_type' : temp_comp.pop(0)
                                                                                });
    elif "op_arg_gbl" in comp:
      temp_comp = comp.split("op_arg_gbl(");
      temp_comp = temp_comp.pop();
      temp_comp = temp_comp.split(",");
      temp_comp[3] = temp_comp[3].replace(')','');
      temp_comp[3] = temp_comp[3].replace(';','');  
      temp_comp[0] = temp_comp[0].replace('&','');
      op_par_loops[op_par_loop_relevant_lines.index(loop)]['op_arg_gbl'].append({ 'name' : temp_comp.pop(0),
                                                                                  'dimension' : temp_comp.pop(0),
                                                                                  'type' : temp_comp.pop(0),
                                                                                  'operation_type' : temp_comp.pop(0)
                                                                                });
    else:
      # this is the tuner argument
      temp_comp = comp;
      temp_comp = temp_comp.replace(');','');
      op_par_loops[op_par_loop_relevant_lines.index(loop)]['tuner'].append({  'name' : temp_comp
                                                                           });

#activate appropriate tuners
for loop_tuner in loop_tuners:
  for loop in op_par_loops:
    if loop_tuner['var_name'] == loop['tuner'][0]['name']:
      loop_tuner['active'] = 1;

#there are overall two situations - if we have defined a tuner, then that overwrites the automated machine learning - otherwise we use machine learning
if not global_tuner['default']:
  #this means we have declared a tuner. here we assume that the user knows what they're doing (if they're playing around with tuners) and we won't invoke any machine learning
  #however, this does not necessarily mean that we don't wish to analyze how good their case is!
  print 'hello world';
     

else: 
  #do magic
  print 'hello';
# now we need to decide if we have any fusable loops


# now we need to decide if it is even possible to fuse these loops or extra transformations are needed

# create vector of properties - the case

# call machine learning to retrieve best result for the current case

# transform the best case into compiler flags

# call compiler 
