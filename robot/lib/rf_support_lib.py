
class rf_support_lib:
    ########################################################################
    #   @brief    Returns the stripped strings
    #   @param    i_str: @type string: string name
    #   @return   Remove all special chars and return the string
    ########################################################################
    def get_strip_string(self, i_str):
        return ''.join(e for e in i_str if e.isalnum())

