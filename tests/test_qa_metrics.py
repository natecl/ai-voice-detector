from scripts.evaluate_qa import metrics


def test_qa_counts_errors_and_does_not_hide_false_positives():
    rows = [
        {'expected':'HUMAN','prediction':'HUMAN'},
        {'expected':'HUMAN','prediction':'AI'},
        {'expected':'AI','prediction':'HUMAN'},
        {'expected':'AI','prediction':None},
    ]
    result=metrics(rows)
    assert result['accuracy_all']==0.25
    assert result['false_positive_rate']==0.5
    assert result['false_negative_rate']==0.5
    assert result['errors']==1
    assert result['accepted']==3
