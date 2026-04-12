from Schemas.graph_representation import SchemaGraph, Table

def gen_stats_light_schema(hdf_path):
    """
    Generate the stats schema (lowercase attributes to match PRICE's STATS-CEB
    workload predicates).
    """

    schema = SchemaGraph()

    # badges
    schema.add_table(Table('badges',
                           primary_key=["id"],
                           attributes=['id', 'userid', 'date'],
                           irrelevant_attributes=['id'],
                           no_compression=[],
                           csv_file_location=hdf_path.format('badges'),
                           table_size=79851))

    # votes
    schema.add_table(Table('votes',
                           primary_key=["id"],
                           attributes=['id', 'postid', 'votetypeid', 'creationdate', 'userid', 'bountyamount'],
                           csv_file_location=hdf_path.format('votes'),
                           irrelevant_attributes=['id'],
                           no_compression=['votetypeid'],
                           table_size=328064))

    # postHistory
    schema.add_table(Table('posthistory',
                           primary_key=["id"],
                           attributes=['id', 'posthistorytypeid', 'postid', 'creationdate', 'userid'],
                           csv_file_location=hdf_path.format('posthistory'),
                           irrelevant_attributes=['id'],
                           no_compression=['posthistorytypeid'],
                           table_size=303187))

    # posts
    schema.add_table(Table('posts',
                           primary_key=["id"],
                           attributes=['id', 'posttypeid', 'creationdate',
                                       'score', 'viewcount', 'owneruserid',
                                       'answercount', 'commentcount', 'favoritecount', 'lasteditoruserid'],
                           csv_file_location=hdf_path.format('posts'),
                           irrelevant_attributes=['lasteditoruserid'],
                           no_compression=['posttypeid'],
                           table_size=91976))

    # users
    schema.add_table(Table('users',
                           primary_key=["id"],
                           attributes=['id', 'reputation', 'creationdate', 'views', 'upvotes', 'downvotes'],
                           csv_file_location=hdf_path.format('users'),
                           no_compression=[],
                           table_size=40325))

    # comments
    schema.add_table(Table('comments',
                           primary_key=["id"],
                           attributes=['id', 'postid', 'score', 'creationdate', 'userid'],
                           csv_file_location=hdf_path.format('comments'),
                           irrelevant_attributes=["id"],
                           no_compression=[],
                           table_size=174305))

    # postLinks
    schema.add_table(Table('postlinks',
                           primary_key=["id"],
                           attributes=['id', 'creationdate', 'postid', 'relatedpostid', 'linktypeid'],
                           csv_file_location=hdf_path.format('postlinks'),
                           irrelevant_attributes=["id"],
                           no_compression=[],
                           table_size=11102))

    # tags
    schema.add_table(Table('tags', attributes=['id', 'count', 'excerptpostid'],
                           csv_file_location=hdf_path.format('tags'),
                           irrelevant_attributes=["id"],
                           no_compression=[],
                           table_size=1032))


    # relationships
    schema.add_relationship('comments', 'postid', 'posts', 'id')
    schema.add_relationship('comments', 'userid', 'users', 'id')

    schema.add_relationship('badges', 'userid', 'users', 'id')

    schema.add_relationship('tags', 'excerptpostid', 'posts', 'id')

    schema.add_relationship('postlinks', 'postid', 'posts', 'id')
    schema.add_relationship('postlinks', 'relatedpostid', 'posts', 'id')

    schema.add_relationship('posthistory', 'postid', 'posts', 'id')
    schema.add_relationship('posthistory', 'userid', 'users', 'id')
    schema.add_relationship('votes', 'postid', 'posts', 'id')
    schema.add_relationship('votes', 'userid', 'users', 'id')

    schema.add_relationship('posts', 'owneruserid', 'users', 'id')

    return schema
