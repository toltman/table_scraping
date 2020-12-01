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
        self.id = self.get_id()
        self.out_filename = self.get_out_filename()

        # Read Excel workbook
        self.book = xlrd.open_workbook(self.filename, formatting_info=True)
        self.sheet = self.book.sheet_by_index(0)
        self.font = self.book.font_list

        self.raw_df = pd.read_excel(self.filename, header=None)

        self.title = self.get_title()
        self.title_lines = self.get_title_lines()
        self.header_lines = self.get_header_lines()

        self.footnotes = self.get_footnotes()

        # Table Column dataframe
        self.col_info = self.parse_col_info()

        # Table Row dataframe
        self.end_row = self.get_row_end()
        self.row_info = self.parse_row_info()
    
        # Table Info dataframe
        self.table_info = self.parse_table_info()



    def get_id(self):
        tnum = ""
        res = re.search(r"tabn(\d{3}\.\d{2})\.xls", self.filename)

        if res:
            tnum = res.group(1)

        return tnum


    def get_out_filename(self):
        tab_id = self.id.replace(".", "_")

        return f"{self.year}_{tab_id}_activate_step1.xlsx"


    def get_title(self):

        # removing newline characters
        title_cell = self.sheet.cell_value(0,0).replace("\n", "")

        # replace repeated whitespace with a single space
        title_cell = re.sub(" +", " ", title_cell)

        title = ""
        res = re.match(r"Table (\d{3}\.\d{2})\. (.*)", title_cell)

        if res:
            title = res.group(2)
        
        return title


    def get_title_lines(self):
        tlines = 1

        if re.match(r"\[.*\]", self.sheet.cell_value(1,0)):
            tlines = 2

        return tlines


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
        tlines = self.title_lines

        # headnote
        headnote = sh.cell_value(1,0) if tlines == 2 else ""

        # stub_head
        stub_head = sh.cell_value(tlines,0)

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
            'digest_table_sub_id',
            'digest_table_sub_title',
            'table_title',
            'headnote',
            'stub_head',
            'general_note',
            'source_note',
            'last_prepared'
        ]

        g = self.row_info.groupby([
            'digest_table_sub_id', 
            'digest_table_sub_title'
            ]).size().reset_index()

        tb_info = g[['digest_table_sub_id', 'digest_table_sub_title']]

        tb_info['digest_table_id'] = self.id
        tb_info['digest_table_year'] = self.year
        tb_info['table_title'] = self.title
        tb_info['headnote'] = headnote
        tb_info['stub_head'] = stub_head
        tb_info['general_note'] = general_note
        tb_info['source_note'] = source_note
        tb_info['last_prepared'] = last_prepared

        tb_info = tb_info[col_list]

        return tb_info

    def get_header_lines(self):
        """Returns the index of the last row of the header"""

        for row in range(0,self.sheet.nrows):
            if self.sheet.cell_value(row,0) == 1:
                return row
            
        print("End of file reached, no integer row")
        return 0
    

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

        # get list of non-empty columns
        # cols = self.get_nonempty_cols()
        cols = list(range(0,self.sheet.ncols))

        header = pd.read_excel(self.filename,
                                skiprows=self.title_lines,
                                header=None,
                                nrows=self.header_lines - self.title_lines,
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
        col_info["digest_table_id"] = self.id
        col_info["digest_table_year"] = self.year

        # create column_ref_note columns
        for x in range(0, self.COL_LEVELS):
            col = col_info[f"column_level_{x + 1}"]

            # create a reference column with the footnote number
            refs = col.str.extract(r"\\([0-9])\\")

            # create new column with the reference note
            col_info[f"column_ref_note_{x + 1}"] = refs.replace(footnotes_dict)

            # delete footnote from column_level_x
            col_level = col.str.replace(r"\\[0-9]\\", "")

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

        # strip and replace \n
        for col in range(0, col_info.shape[1]):
            new_col = col_info.iloc[:,col].str.strip(" .")
            new_col = new_col.str.replace("\n", " ")
            new_col = new_col.str.replace("- ", "")
            col_info.iloc[:,col] = new_col

        return col_info

    def get_row_end(self):

        xf_list = self.book.xf_list

        for row in range(self.header_lines + 2, self.sheet.nrows):
            idx = self.sheet.cell_xf_index(row,0)
            top_line_style = xf_list[idx].border.top_line_style
            bottom_line_style = xf_list[idx].border.bottom_line_style

            if top_line_style == 1:
                return row - 1
            elif bottom_line_style == 1:
                return row

        print("Error: No data end row")
        return 0


    def get_leading_spaces(self, string):
        string = str(string)
        res = re.search(r"[^ ]", string)
        
        if res:
            return res.start()
        else:
            return 0
    
    def parse_row_info(self):
        row_level = 0
        indent_level = 0
        rows = self.end_row - self.header_lines
        subtitle = ""
        
        empty = np.empty([rows, self.ROW_LEVELS])
        empty[:] = np.NaN
        
        row_levels = pd.DataFrame(empty,
                                index=range(self.header_lines+1, self.end_row+1))

        for row in range(self.header_lines + 1, self.end_row + 1):
            cell = self.sheet.cell(row, 0)
            cell_xf = self.book.xf_list[cell.xf_index]
            is_bold = bool(self.font[cell_xf.font_index].bold)
            is_empty = bool(cell.value == "")
            indents = self.get_leading_spaces(cell.value)
            is_total = is_bold and (indents == 3 or indents == 5)

            
            if is_empty and self.sheet.cell(row,1).value.strip() != "":
                subtitle = self.sheet.cell(row, 1).value
            
            
            if indents in [0,3,5]:
                indent_level = 0
            else:
                indent_level = indents / 2
            
            
            if is_total:
                row_level = 0
                row_levels.loc[row, "subtitle"] = subtitle
                row_levels.loc[row, "is_total"] = "TRUE"
                row_levels.loc[row, row_level] = cell.value
                row_level = 1
            elif is_bold:
                row_level = 0
                row_levels.loc[row, "subtitle"] = subtitle
                row_levels.loc[row, "is_total"] = "FALSE"
                row_levels.loc[row, row_level] = cell.value
                row_level = 1
            else: 
                row_levels.loc[row, "subtitle"] = subtitle
                row_levels.loc[row, "is_total"] = "FALSE"
                row_levels.loc[row, row_level+indent_level] = cell.value
            
        # forward fill row levels
        row_levels = row_levels.ffill(axis=1).ffill(axis=0)
        is_duplicate = row_levels.apply(lambda row: row.duplicated(), axis=1)
        row_levels = row_levels.where(~is_duplicate, "")

        # rename columns
        row_levels.columns = [f"row_level_{col+1}" for col in range(0,7)] + ["digest_table_sub_title", "is_total"]
        
        # create row_ref_note columns
        for x in range(0, self.ROW_LEVELS):
            col = row_levels[f"row_level_{x+1}"].astype(str)
            
            # create a reference column with the footnote number
            refs = col.str.extract(r"\\([0-9])\\")
            
            # create new column with the reference note
            row_levels[f"row_ref_note_{x+1}"] = refs.replace(self.footnotes)
            
            # delete footnote from row_level_x
            new_col = col.str.replace(r"\\[0-9]\\", "").str.strip()
            row_levels[f"row_level_{x+1}"] = new_col
        
        row_levels = row_levels.fillna("")

        # generate subtable ids
        subtable_titles = row_levels['digest_table_sub_title'].unique()
        subtable_ids = [self.AA(i, "") for i in range(0, len(subtable_titles))]
        subtable_dict = dict(zip(subtable_titles, subtable_ids))
        row_levels['digest_table_sub_id'] = row_levels['digest_table_sub_title'].replace(subtable_dict)


        # table id and year
        row_levels["digest_table_id"] = self.id
        row_levels["digest_table_year"] = self.year

        # list of columns in the desired order
        col_list = [[f"row_level_{x + 1}", f"row_ref_note_{x + 1}"] for x in range(0,7)]
        col_list = list(np.array(col_list).flatten())

        # rearrange column order
        row_levels = row_levels[
            [
                'digest_table_id', 
                'digest_table_year', 
                'digest_table_sub_id',
                'digest_table_sub_title',
            ] + 
            col_list +
            ['is_total']
        ]

        # strip and replace \n
        for col in range(0, row_levels.shape[1]):
            new_col = row_levels.iloc[:,col].str.strip(" .")
            new_col = new_col.str.replace("\n", " ")
            new_col = new_col.str.replace("- ", "")
            row_levels.iloc[:,col] = new_col

        # Clean up footnotes columns
        df_fn = self.raw_df.loc[:, 1:].copy()
        fn_cols = df_fn.apply(lambda x: self.is_fn_col(x), axis=0)

        for i in fn_cols.index:
            if fn_cols[i]:
                fn_col = df_fn.loc[:, i].fillna("")
                prev_col = df_fn.loc[:, i-1].fillna("").astype(str)
                df_fn.loc[:, i-1] = prev_col + fn_col
        
        # remove footnote only cols
        df_fn = df_fn.loc[:, ~fn_cols]
        df_fn.columns = range(0,df_fn.shape[1])

        # merge with row data and rename columns
        df = pd.merge(row_levels, df_fn, how='left', left_index=True, right_index=True)
        col_names = list(range(0,df_fn.shape[1]))
        col_names_new = [self.AA(i, "") for i in range(0, df_fn.shape[1])]
        col_names_dict = dict(zip(col_names, col_names_new))
        df = df.rename(columns=col_names_dict)

        # drop row if all NaN in data
        drop_rows = df.loc[:, 'A':].apply(lambda x: self.na_or_empty(x), axis=1)
        df = df[~drop_rows]

        # create row index
        df.insert(4, 'row_index', np.arange(1,df.shape[0]+1))

        return df


    def na_or_empty(self, row):
        is_na = row.isna() 
        is_space = row.str.match(r"^\s*$")
        is_empty = (is_na | is_space).all()
        return is_empty
    

    def is_fn_col(self, col):
        """col contains only footnotes"""
        return col.str.contains(r"\\[0-9]\\").any()


    def write_xlsx(self):
        """Writes to output file"""

        with pd.ExcelWriter(self.out_filename) as writer: #pylint: disable=abstract-class-instantiated
            
            # table info
            table_info = self.table_info.T.reset_index().T

            table_info.to_excel(
                writer, 
                sheet_name="table_info", 
                index=False,
                header=False
            )

            # rows
            row_info = self.row_info.T.reset_index().T

            row_info.to_excel(
                writer,
                sheet_name="row_info",
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
    # table = Table("tables/tabn203.10.xls", "2019")
    # print(table.row_info.head())
    directory = "tables/"
    for filename in os.listdir(directory):
        if filename.endswith(".xls"):
            file_directory = os.path.join(directory, filename)
            table = Table(file_directory, "2019")
            print(table.id)
            table.write_xlsx()
