<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:template match="/">
  <html>
  <head>
<link href="https://fonts.googleapis.com/css?family=Ubuntu:300" rel="stylesheet" />
     <style>
        a.word { text-decoration:none;  color: black; }
        a.word:hover { text-decoration:underline;  color: black; }
        * { font-family: 'Ubuntu', sans-serif; }
     </style>
<xsl:for-each select="podcast/show">
  <title><xsl:value-of select="@title" /></title>
</xsl:for-each>
  </head>
  <body>

<xsl:for-each select="podcast/show">
  <center><h2><xsl:value-of select="@title" /></h2></center>
  <center><a href="{@showlink}">direct download link</a></center>
</xsl:for-each>
<br/><br/><br/><br/>
<xsl:for-each select="podcast/show/transcription">
<xsl:for-each select="word"><a class='word' target='naplayer' href="{concat('http://naplay.it/', ../../@episodenumber,'/',@start_time)}"><xsl:value-of select=". " /><xsl:text> </xsl:text></a></xsl:for-each>
<xsl:text> 
</xsl:text><br/><br/>
</xsl:for-each>

  </body>
  </html>
</xsl:template>
</xsl:stylesheet>



