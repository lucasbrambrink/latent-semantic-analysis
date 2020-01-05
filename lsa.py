import bs4
import requests
from time import sleep
import csv


class Assessment:
    """
    Abstract Base class for type of comparison.

    Initializes HTML form data & attempts to get score for a particular pair/group of pairs.
    """
    BASE = "http://lsa.colorado.edu/cgi-bin"
    TERM_SEPARATOR = "%0D%0A%0D%0A"
    URL = ''
    FORM_PARAMS = {}

    def __init__(self, text_1=None, text_2=None):
        self.form_data = dict(self.FORM_PARAMS)
        self.assign_text(text_1, text_2)
        self.success, self.score = self.get_score()
        self.text_1 = text_1
        self.text_2 = text_2
        print(self.success, self.score, text_1, text_2)

    def assign_text(self, text_1, text_2):
        raise NotImplemented

    def parse(self, result):
        raise NotImplemented

    def simple_urlencode(self):
        return '&'.join('='.join(d) for d in self.form_data.items())

    def get_score(self):
        result = requests.post(f"{self.BASE}/{self.URL}", data=self.simple_urlencode())
        if result.status_code != 200:
            # unsuccessful response
            print(self)

        return self.parse(result)


class Pairwise(Assessment):
    """
     LSAspace=General_Reading_up_to_1st_year_college+%28300+factors%29
     &LSATermCnt=20
     &LSAFactors=
     &LSAFrequency=0
     &CmpType=doc
     &txt1=this%0D%0A%0D%0Athat
     """
    URL = 'LSA-pairwise-x.html'
    FORM_PARAMS = {
        'LSATermCnt': '20',
        'LSAspace': 'General_Reading_up_to_1st_year_college+%28300+factors%29',
        'LSAFactors': '',
        'LSAFrequency': '0',
        'CmpType': 'doc',
        'txt1': ''
    }

    def parse(self, result):
        soup = bs4.BeautifulSoup(result.content)
        try:
            score_cell = soup.find_all('td')[3]
            score = score_cell.text.strip().splitlines()[0]
            return True, score
        except IndexError:
            import ipdb
            ipdb.set_trace()
            print("Unable to find score")
            return False, None

    def assign_text(self, text_1, _):
        self.form_data['txt1'] = f'{self.TERM_SEPARATOR}'.join(text_1)

class OneToMany(Assessment):
    """
    LSAspace=General_Reading_up_to_1st_year_college+%28300+factors%29&
    CmpType=term2term
    &LSAFactors=
    &txt1=bread+butter
    &txt2=wood+bark%0D%0A%0D%0Awood+bakr%0D%0A%0D%0Awood+bark
    """
    URL = 'LSA-one2many-x.html'
    FORM_PARAMS = {
        'LSAspace': 'General_Reading_up_to_1st_year_college+%28300+factors%29',
        'LSAFactors': '',
        'CmpType': 'term2term',
        'txt1': '',
        'txt2': '',
    }

    def assign_text(self, text_1, text_2):
        self.form_data['txt1'] = f'+'.join(text_1)
        self.form_data['txt2'] = f'{self.TERM_SEPARATOR}'.join('+'.join(t) for t in text_2)

    def parse(self, result):
        soup = bs4.BeautifulSoup(result.content)
        try:
            score_cell = soup.find_all('tr')
            text = score_cell[1].find('td').text
            scores = [t.split()[-1] for t in text.strip().splitlines()]
            return True, scores
        except IndexError:
            import ipdb
            ipdb.set_trace()
            print("Unable to find score")
            return False, None


class LSAFormUtil:
    """
    Util class for reading a CSV file, parsing into pairs/groupings
    and scoring them.
    Finally, `.export` and `.export_matrix` allows adding the data
    back into a sheet.
    """
    PAIRWISE = 0
    ONE_TO_MANY = 1
    ASSESSMENT = {
        PAIRWISE: Pairwise,
        ONE_TO_MANY: OneToMany,
    }

    def __init__(self, sheet):
        self.sheet = sheet
        self.data = self.read_sheet(sheet)
        self.pairwise = []
        self.one_to_many = []

        self.run_pairs(self.data)

    def read_sheet(self, sheet_path):
        with open(sheet_path) as sheet:
            data = csv.reader(sheet)
            all_pairs = []
            for row in data:
                pairs_in_row = [
                    (pair_1, pair_2) for pair_1, pair_2 in zip(row[::2], row[1::2])
                    if pair_1 and pair_2
                ]
                if pairs_in_row:
                    all_pairs.append(pairs_in_row)
                else:
                    break

            return all_pairs

    def run_pairs(self, data_set, run_pairs=True, run_one_to_many=True):
        self.pairwise = []
        if run_pairs:
            for row in data_set:
                row_results = []
                for pair in row:
                    result = Pairwise(text_1=pair)
                    row_results.append(result)
                    sleep(0.1)
                self.pairwise.append(row_results)

        self.one_to_many = []
        if run_one_to_many:
            for row in data_set:
                one_to_many_row = []
                for index in range(4):
                    end_pair = row[index]
                    other_pairs = [r for i, r in enumerate(row) if i != index]
                    result = OneToMany(text_1=end_pair, text_2=other_pairs)
                    one_to_many_row.append(result)
                    sleep(0.1)
                self.one_to_many.append(one_to_many_row)

    def export(self):
        with open('result.csv', 'w') as export_to:
            writer = csv.writer(export_to)
            for index, row in enumerate(self.data):
                pairwise = lsa.pairwise[index]
                one_to_many = lsa.one_to_many[index]

                row_to_write = [r for z in row for r in z]

                row_to_write.extend(s.score for s in pairwise)

                for result in one_to_many:
                    row_to_write.append('')
                    row_to_write.extend(result.score)

                writer.writerow(row_to_write)

    def export_matrix(self):
        """
        export to

            '', a,   b,  c,  d
            a ,  -, ab, ac, ad
            b , ba,  -, bc, bd
            c , ca, cb,  -, cd
            d , ad, db, cd,  -
        """
        with open('matrix.csv', 'w') as matrix:
            writer = csv.writer(matrix)
            for one_to_many in self.one_to_many:
                # add spacing row
                writer.writerow([])
                length = len(one_to_many) + 1
                # represents 1 Matrix
                for i in range(length):
                    row_to_write = []
                    if i == 0:
                        headers = ['', '+'.join(one_to_many[0].text_1)]
                        headers.extend('+'.join(z) for z in one_to_many[0].text_2)
                        row_to_write.extend(headers)
                    else:
                        item = one_to_many[i - 1]
                        row_to_write.append('+'.join(item.text_1))
                        row_to_write.extend(item.score)
                        row_to_write.insert(i, '-')

                    writer.writerow(row_to_write)


### script
path_to_sheet = '/Users/lucasbrambrink/Downloads/Analogy_Metaphor_Stim_27Dec19_3.csv'
lsa = LSAFormUtil(path_to_sheet)
# lsa.export()
# lsa.export_matrix()
