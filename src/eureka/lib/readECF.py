import os
import shlex
# Required in case user passes in a numpy object (e.g. np.inf)
import numpy as np


IN_WIN_OS = os.name == 'nt'


class MetaClass:
    '''A class to hold Eureka! metadata.

    This class loads a Eureka! Control File (ecf) and lets you
    query the parameters and values.

    Notes
    -----
    History:

    - 2009-01-02 Christopher Campo
        Initial Version.
    - 2010-03-08 Patricio Cubillos
        Modified from ccampo version.
    - 2010-10-27 Patricio Cubillos
        Docstring updated
    - 2011-02-12 Patricio Cubillos
        Merged with ccampo's tepclass.py
    - 2022-03-24 Taylor J Bell
        Significantly modified for Eureka
    '''

    def __init__(self, folder=None, file=None, **kwargs):
        '''Initialize the MetaClass object.

        Parameters
        ----------
        folder : str; optional
            The folder containing an ECF file to be read in. Defaults to None
            which resolves to './'.
        file : str; optional
            The ECF filename to be read in. Defaults to None which results
            in an empty MetaClass object.
        **kwargs : dict
            Any additional parameters to be loaded into the MetaClass after
            the ECF has been read in

        Notes
        -----
        History:

        - Mar 2022 Taylor J Bell
            Initial Version based on old readECF code.
        '''

        if folder is None:
            folder = '.'+os.sep

        self.params = {}
        if file is not None and folder is not None:
            if os.path.exists(os.path.join(folder, file)):
                self.read(folder, file)
            else:
                raise ValueError(f"The file {os.path.join(folder,file)} "
                                 f"does not exist.")

        if kwargs is not None:
            # Add any kwargs to the parameter dict
            self.params.update(kwargs)

            # Store each as an attribute
            for param, value in kwargs.items():
                setattr(self, param, value)
        
        # Initialize property attributes for getters and setters
        self._outputdir_raw = None
        self._inputdir_raw = None

    def __str__(self):
        '''A function to nicely format some outputs when a MetaClass object is
        converted to a string.

        This function gets used if one does str(meta) or print(meta).

        Returns
        -------
        str
            A string representation of what is contained in the
            MetaClass object.

        Notes
        -----
        History:

        - Mar 2022 Taylor J Bell
            Initial version.
        '''
        output = ''
        for par in self.params:
            # For each parameter, format a line as "Name: Value"
            output += par+': '+str(getattr(self, par))+'\n'
        return output

    def __repr__(self):
        '''A function to nicely format some outputs when asked for a printable
        representation of the MetaClass object.

        This function gets used if one does repr(meta) or does just meta in an
        interactive shell.

        Returns
        -------
        str
            A string representation of what is contained in the MetaClass
            object in a manner that could reproduce a similar MetaClass object.

        Notes
        -----
        History:

        - Mar 2022 Taylor J Bell
            Initial version.
        '''
        # Get the fully qualified name of the class
        output = type(self).__module__+'.'+type(self).__qualname__+'('
        # Show what folder and file were used to read in an ECF
        output += f"folder='{self.folder}', file='{self.filename}', "
        # Show what values have been loaded into the params dictionary
        output += "**"+str(self.params)
        output = output+')'
        return output

    def __setattr__(self, item, value):
        """Maps attributes to values

        Parameters
        ----------
        item : str
            The name for the attribute
        value : any
            The attribute value
        """

        # Set the attribute
        super().__setattr__(item, value)

        # Update the parameter dict, for a subset of attributes.

        # Skip state attributes
        if item in ['lines', 'params', 'filename', 'folder']:
            return
        
        # Skip private attributes and "__" attributes / methods
        if item[0] == '_':
            return

        # Otherwise, add it to the list of parameters
        self.params[item] = value

    def read(self, folder, file):
        """A function to read ECF files

        Parameters
        ----------
        folder : str
            The folder containing an ECF file to be read in.
        file : str
            The ECF filename to be read in.

        Notes
        -----
        History:

        - Mar 2022 Taylor J Bell
            Initial Version based on old readECF code.
        - April 25, 2022 Taylor J Bell
            Joining topdir and inputdir/outputdir here.
        """
        self.filename = file
        self.folder = folder
        # Read the file
        with open(os.path.join(folder, file), 'r') as file:
            self.lines = file.readlines()

        cleanlines = []   # list with only the important lines
        # Clean the lines:
        for line in self.lines:
            # Strip off comments:
            if "#" in line:
                line = line[0:line.index('#')]
            line = line.strip()

            # Keep only useful lines:
            if len(line) > 0:
                cleanlines.append(line)

        for line in cleanlines:
            # FINDME: Can the posix here be set to always be `false` as is the case in the next code-line?
            name = shlex.split(line, posix=(not IN_WIN_OS))[0]
            # Split off the name and remove all spaces except quoted substrings
            # Also keep quotation marks for things that need to be escaped
            # (e.g. max is a built-in funciton)
            # The space in ' '.join allows for spaces in quoted directory paths.
            val = ' '.join(shlex.split(line, posix=False)[1:])
            try:
                val = eval(val)
            except:
                # FINDME: Need to catch only the expected exception
                pass
            self.params[name] = val

        # Store each as an attribute
        for param, value in self.params.items():
            setattr(self, param, value)
        
        # Clean up topdir
        # Replace topdir with current working directory if requested.
        self.topdir = self.topdir.replace('__cwd__', os.getcwd())
        self.topdir = self.topdir.replace('__CWD__', os.getcwd())

        # Initialize raw input/output dirs
        self._inputdir_raw = self.inputdir
        self._outputdir_raw = self.outputdir

        # Perform cleanups on paths
        for path_attr in ['topdir', '_inputdir_raw', '_outputdir_raw']:
            path = getattr(self, path_attr)
            # Remove any quotations, they are no longer needed after the file has been parsed for spaces.
            path = path.replace('"', '')

            # Make replacements for os.sep that is agnostic to what format the user provided.
            # We need to do this placeholder hack otherwise subsequent replaces may double up on os.sep's
            path = path.replace('/', '__SEP_PLACEHOLDER__')     # Unix-Like input
            path = path.replace('\\\\', '__SEP_PLACEHOLDER__')  # Sorta-Windows-like input (double \)
            path = path.replace('\\', '__SEP_PLACEHOLDER__')    # Windows-like input (single \)

            # Convert to correct separator and update attribute
            path = path.replace('__SEP_PLACEHOLDER__', os.sep)
            setattr(self, path_attr, path)

        # Update input/output dirs using user-provided raw strong and topdir.
        # os.sep's allows the user to provided nested directories.
        # os.path.abs allows the user to provide directories that are above topdir (os.pardir).
        # For example: /home/User/Data/TargetName/Analysis/../Data/WFC3
        self.inputdir = os.path.abspath(
            os.path.join(self.topdir, *self.inputdir_raw.split(os.sep))
            )
        self.outputdir = os.path.abspath(
            os.path.join(self.topdir, *self.outputdir_raw.split(os.sep))
            )

        # Make sure there's a trailing slash at the end of the paths
        if self.inputdir[-1] != os.sep:
            self.inputdir += os.sep
        if self.outputdir[-1] != os.sep:
            self.outputdir += os.sep

    def write(self, folder):
        """Write an ECF file based on the current MetaClass settings.

        NOTE: For now this rewrites the input_meta data to a new ECF file
        in the requested folder. In the future this function should make a full
        ECF file based on all parameters in meta.

        Parameters
        ----------
        folder : str
            The folder where the ECF file should be written.

        Notes
        -----
        History:

        - Mar 2022 Taylor J Bell
            Initial Version.
        - Oct 2022 Eva-Maria Ahrer
            Update parameters and replace
        """
        
        for i in range(len(self.lines)):
            line = self.lines[i]
            # Strip off comments:
            if "#" in line:
                line = line[0:line.index('#')]
            line = line.strip()

            if len(line) > 0:
                name = line.split()[0]
                val = ''.join(line.split()[1:])
                new_val = self.params[name]
                # check if values have been updated
                if val != new_val:
                    self.lines[i] = self.lines[i].replace(str(val), 
                                                          str(new_val))
        
        with open(os.path.join(folder, self.filename), 'w') as file:
            file.writelines(self.lines)

    def copy_ecf(self):
        """Copy an ECF file to the output directory to ensure reproducibility.

        NOTE: This will update the inputdir of the ECF file to point to the
        exact inputdir used to avoid ambiguity later and ensure that the ECF
        could be used to make the same outputs.

        Notes
        -----
        History:

        - Mar 2022 Taylor J Bell
            Initial Version based on old readECF code.
        """
        # Copy ecf (and update inputdir to be precise which exact inputs
        # were used)
        new_ecfname = os.path.join(self.outputdir, self.filename)
        with open(new_ecfname, 'w') as new_file:
            for line in self.lines:
                if len(line.strip()) == 0 or line.strip()[0] == '#':
                    new_file.write(line)
                else:
                    line_segs = line.strip().split()
                    if line_segs[0] == 'inputdir':
                        new_file.write(line_segs[0]+'\t\t'+self.inputdir_raw +
                                       '\t'+' '.join(line_segs[2:])+'\n')
                    else:
                        new_file.write(line)

    @property
    def outputdir_raw(self):
        return self._outputdir_raw
    
    @outputdir_raw.setter
    def outputdir_raw(self, new_outputdir):
        
        if new_outputdir is None:
            return

        # Clean up input
        # Remove any quotations, they are no longer needed after the file has been parsed for spaces.
        new_outputdir = new_outputdir.replace('"', '')

        # Make replacements for os.sep that is agnostic to what format the user provided.
        # We need to do this placeholder hack otherwise subsequent replaces may double up on os.sep's
        new_outputdir = new_outputdir.replace('/', '__SEP_PLACEHOLDER__')     # Unix-Like input
        new_outputdir = new_outputdir.replace('\\\\', '__SEP_PLACEHOLDER__')  # Sorta-Windows-like input (double \)
        new_outputdir = new_outputdir.replace('\\', '__SEP_PLACEHOLDER__')  # Windows-like input (single \)

        # Convert to correct separator and update attribute
        new_outputdir = new_outputdir.replace('__SEP_PLACEHOLDER__', os.sep)

        # Change to outputdir_raw. Update the outputdir with the new value.
        # It looks like a change to outputdir_raw after initialization is not common. Only happens in tests.
        # But continue to support it in case it breaks others code.
        self._outputdir_raw = new_outputdir
        self.outputdir = \
            os.path.abspath(
                os.path.join(self.topdir, *new_outputdir.split(os.sep))
                )
        # Make sure there's a trailing slash at the end of the paths
        if self.outputdir[-1] != os.sep:
            self.outputdir += os.sep
    
    @property
    def inputdir_raw(self):
        return self._inputdir_raw
    
    @inputdir_raw.setter
    def inputdir_raw(self, new_inputdir):
        
        if new_inputdir is None:
            return

        # Clean up input
        # Remove any quotations, they are no longer needed after the file has been parsed for spaces.
        new_inputdir = new_inputdir.replace('"', '')

        # Make replacements for os.sep that is agnostic to what format the user provided.
        # We need to do this placeholder hack otherwise subsequent replaces may double up on os.sep's
        new_inputdir = new_inputdir.replace('/', '__SEP_PLACEHOLDER__')     # Unix-Like input
        new_inputdir = new_inputdir.replace('\\\\', '__SEP_PLACEHOLDER__')  # Sorta-Windows-like input (double \)
        new_inputdir = new_inputdir.replace('\\', '__SEP_PLACEHOLDER__')  # Windows-like input (single \)

        # Convert to correct separator and update attribute
        new_inputdir = new_inputdir.replace('__SEP_PLACEHOLDER__', os.sep)

        # Change to inputdir_raw. Update the inputdir with the new value.
        # It looks like a change to inputdir_raw after initialization is not common. Only happens in tests.
        # But continue to support it in case it breaks others code.
        self._inputdir_raw = new_inputdir
        self.inputdir = \
            os.path.abspath(
                os.path.join(self.topdir, *new_inputdir.split(os.sep))
                )
        # Make sure there's a trailing slash at the end of the paths
        if self.inputdir[-1] != os.sep:
            self.inputdir += os.sep
