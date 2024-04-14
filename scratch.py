def similarity_ratio(str1, str2):
    def string_sim():
        set1 = set(str1)
        set2 = set(str2)
        common_chars = set1.intersection(set2)
        if len(set1) == 0 and len(set2) == 0:
            return 0
        else:
            similarity_ratio = len(common_chars) / (len(set1) + len(set2) - len(common_chars))
            
            return similarity_ratio
    if str1 == str2:
        return 1.4
    elif str1 in str2 or str2 in str1:
        return 1.3
    elif "/" in str1 and "/" in str2:
        
        if str1.split("/")[1] == str2.split("/")[1]:
            
            return 1.2
        elif str1.split("/")[1] in str2.split("/")[1] or str2.split("/")[1] in str1.split("/")[1]:
            
            return 1.1
        else:
            return string_sim()
    else:    
        return string_sim()
            
    
print(similarity_ratio("017/122", "000/003"))