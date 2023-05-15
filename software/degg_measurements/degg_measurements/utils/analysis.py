class Analysis(object):
    def __init__(self, ana_name, degg_name, u_verdict, l_verdict, total_n):
        self._ana_name  = str(ana_name)
        self._degg_name = str(degg_name)
        self._u_verdict = int(u_verdict)
        self._l_verdict = int(l_verdict)
        self._total_n   = int(total_n)

    def getName(self):
        return self._ana_name

    def getDEggName(self):
        return self._degg_name

    def getVerdict(self):
        return [self._u_verdict, self._l_verdict, self._total_n]

