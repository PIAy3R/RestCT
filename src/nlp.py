import wordninja
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def word_similarity(str1: str, str2: str):
    """
    Calculates the cosine similarity between two strings.
    """
    str1 = [w.lower() for w in wordninja.split(str1)]
    str2 = [w.lower() for w in wordninja.split(str2)]

    vectorizer = CountVectorizer().fit_transform([' '.join(str1), ' '.join(str2)])
    cosine_sim = cosine_similarity(vectorizer)
    return cosine_sim[0][1]
