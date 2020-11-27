import os
import xlrd
import numpy as np
import pandas as pd
import re

# Table class

class Table():
    ROW_LEVELS = 7
    COL_LEVELS = 7

    def __init__(self, file_directory, year):
        self.filename = file_directory
        self.year = year

        self.number = re.search(r"tabn(\d{3}\.\d{2})\.xls", file_directory).group(1)

        # Read Excel workbook
        book = xlrd.open_workbook(self.filename, formatting_info=True)
        self.sheet = book.sheet_by_index(0)
        self.font = book.font_list

        self.raw_df = pd.read_excel(self.filename, header=None)

        # Table title
        self.title = self.get_title()

        # Table Info dataframe
        self.table_info = self.parse_table_info()

        # Table Column dataframe
        self.col_info = self.parse_col_info()
    

    @property
    def out_filename(self):
        digest_number = self.number.replace(".", "_")
        return f"{self.year}_{digest_number}_activate_step1.xlsx"

    def get_title(self):

        # removing newline characters
        title_cell = self.sheet.cell_value(0,0).replace("\n", "")

        # replace repeated whitespace with a single space
        title_cell = re.sub(" +", " ", title_cell)

        title = re.match(
            r"Table (\d{3}\.\d{2})\. (.*)", 
            title_cell
        ).group(2)
        return title

    def AA(self, num, string):
        """Recursively builds column index
        
        Inspired by from this Stackoverflow answer:
        https://stackoverflow.com/a/54837286
        """
        
        r = num % 26
        num = (num - r) // 26
        string = chr(ord("A") + r) + string
        
        if num > 26:
            string = self.AA(num, string)
        elif num > 0:
            string = chr(ord("A") + num - 1) + string
            
        return string
    
    def parse_table_info(self):
        """Returns table_info dataframe"""

        sh = self.sheet
        df = self.raw_df

        # headnote
        headnote = sh.cell_value(1,0) if self.get_titlelines() == 2 else ""

        # stub_head
        stub_head = sh.cell_value(self.get_titlelines(),0)

        # general_note
        general = df[0].str.extract(r"NOTE: (.*)").dropna()
        general_note = general[0].values[0].strip()

        # source
        source = df[0].str.extract(r"SOURCE: (.*)\((.*)\)").dropna()
        source_note = source[0].values[0].strip()

        # last_prepared
        last_prepared = source[1].values[0].strip()

        col_list = [
            'digest_table_id', 
            'digest_table_year', 
            'table_title',
            'headnote',
            'stub_head',
            'general_note',
            'source_note',
            'last_prepared'
        ]

        val_list = [
            self.number, 
            self.year, 
            self.title,
            headnote,
            stub_head,
            general_note,
            source_note,
            last_prepared
        ]

        tb_info = pd.DataFrame(np.array([col_list, val_list]))
        return tb_info

    def header_end(self):
        """Returns the row number of the integer row"""

        sh = self.sheet
    
        for row in range(0,sh.nrows):
            if sh.cell_value(row,0) == 1:
                return row
            
        print("End of file reached, no integer row")
        return 0
    

    def get_titlelines(self):
        """Returns the number of lines to skip for the title(s)"""

        if re.match(r"\[.*\]", self.sheet.cell_value(1,0)):
            skip = 2
        else:
            skip = 1
        
        return skip
    

    # def is_empty(self, series):
    #     """Returns True if row or column is empty"""

    #     if series.isna().all():
    #         return True
    #     else:
    #         return (series.isna() | series.str.match(r"\W")).all()


    # def get_nonempty_cols(self):
    #     cols = [not self.is_empty(self.raw_df.iloc[:, col]) for col in range(0, self.sheet.ncols)]
    #     return list(self.raw_df.loc[:, cols].columns)


    def get_header(self):
        # create header
        header_n = self.header_end()

        # determine title rows to skip
        skip = self.get_titlelines()

        # get list of non-empty columns
        # cols = self.get_nonempty_cols()
        cols = list(range(0,self.sheet.ncols))

        header = pd.read_excel(self.filename,
                                skiprows=skip,
                                header=None,
                                nrows=header_n-skip,
                                usecols=cols
                                )

        # drop the first column
        header = header.iloc[:, 1:]

        header = header.ffill(axis=0).ffill(axis=1)
        return pd.MultiIndex.from_arrays(header.values)

    def get_footnotes(self):
        """Returns footnotes dict"""

        df = self.raw_df

        # Extract footnotes from raw df
        footnotes = df[0].str.extract(r"\\([0-9])\\(.*)").dropna().set_index(0)
        return footnotes.to_dict()[1]

    def parse_col_info(self):
        """Returns dataframe with column information"""

        header = self.get_header()
        footnotes_dict = self.get_footnotes()
        
        # remove duplicated column levels
        col_info = header.to_frame(index=False)
        is_duplicate = col_info.apply(lambda row: row.duplicated(), axis=1)
        col_info = col_info.where(~is_duplicate, "")

        # create extra columns for unused columns index levels
        for n in range(col_info.shape[1], self.COL_LEVELS):
            col_info.insert(n, n, "")
        
        # label column levels
        col_info.columns = [f"column_level_{col+1}" for col in col_info.columns]
        
        # add table_id and table_year to col_info
        col_info["digest_table_id"] = self.number
        col_info["digest_table_year"] = self.year

        # create column_ref_note columns
        for x in range(0, self.COL_LEVELS):
            col = col_info[f"column_level_{x + 1}"]

            # create a reference column with the footnote number
            refs = col.str.extract(r"\\([0-9])\\")

            # create new column with the reference note
            col_info[f"column_ref_note_{x + 1}"] = refs.replace(footnotes_dict)

            # delete footnote from column_level_x
            col_level = col.str.replace(
                pat = r"\\[0-9]\\",
                repl = ""
            )

            col_info[f"column_level_{x + 1}"] = col_level

        # Remove extra headers
        col_info = col_info.fillna("")

        # Drop duplicated rows in header
        col_info = col_info.drop_duplicates().reset_index()

        # create column_index field
        col_info["column_index"] = [self.AA(i,"") for i in col_info.index]

        # list of columns in the desired order
        col_list = [[f"column_level_{x + 1}", f"column_ref_note_{x + 1}"] for x in range(0,7)]
        col_list = list(np.array(col_list).flatten())

        # rearrange column order
        col_info = col_info[
            ['digest_table_id', 'digest_table_year', 'column_index'] + 
            col_list
        ]

        return col_info

    def write_xlsx(self):
        """Writes to output file"""

        with pd.ExcelWriter(self.out_filename) as writer: #pylint: disable=abstract-class-instantiated
            self.table_info.to_excel(
                writer, 
                sheet_name="table_info", 
                index=False,
                header=False
            )

            # reset column headers so they are part of the dataframe
            col_info = self.col_info.T.reset_index().T

            col_info.to_excel(
                writer, 
                sheet_name="column_info",
                index=False,
                header=False
            )


if __name__ == "__main__":
    directory = "tables/"
    for filename in os.listdir(directory):
        if filename.endswith(".xls"):
            file_directory = os.path.join(directory, filename)
            table = Table(file_directory, "2019")
            table.write_xlsx()



