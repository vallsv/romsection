class TooltipFactory:

    _STYLE = 'style="width: 100%; margin-top: 0px; margin-bottom: 0px; margin-left: 0px; margin-right: 0px; border-collapse: collapse"'

    def __init__(self):
        self.__content = ""

    def isEmpty(self) -> bool:
        return self.__content == ""

    def addRow(self, label: str, value: str):
        line = f'<tr><td><b>{label}</b>&#160;&#160;</td><td>{value}</td></tr>'
        self.__content += line

    def addSeparator(self):
        line = '<tr><td style="font-size:1px" colspan="2"><hr /></td></tr>'
        self.__content += line

    def html(self) -> str:
        return f"<html><table {self._STYLE}>{self.__content}</table></html>"
