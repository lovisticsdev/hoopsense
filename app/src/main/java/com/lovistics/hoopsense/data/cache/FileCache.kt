package com.lovistics.hoopsense.data.cache

import android.content.Context
import java.io.File
import javax.inject.Inject

class FileCache @Inject constructor(private val context: Context) {

    fun write(fileName: String, data: String) {
        try {
            val file = File(context.filesDir, fileName)
            file.writeText(data)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun read(fileName: String, maxAgeMs: Long): String? {
        val file = File(context.filesDir, fileName)
        if (!file.exists()) return null

        val age = System.currentTimeMillis() - file.lastModified()
        if (age > maxAgeMs) return null

        return try {
            file.readText()
        } catch (e: Exception) {
            null
        }
    }
}
