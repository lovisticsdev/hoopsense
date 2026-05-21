package com.lovistics.hoopsense.data.cache

import android.content.Context
import android.util.Log
import java.io.File
import java.io.IOException
import javax.inject.Inject

class FileCache @Inject constructor(private val context: Context) {

    companion object {
        private const val TAG = "FileCache"
    }

    fun write(fileName: String, data: String) {
        try {
            val file = File(context.filesDir, fileName)
            val tempFile = File(context.filesDir, "$fileName.tmp")
            tempFile.writeText(data)
            if (!tempFile.renameTo(file)) {
                file.writeText(data)
                tempFile.delete()
            }
        } catch (e: IOException) {
            Log.w(TAG, "Failed to write cache file: $fileName", e)
        }
    }

    fun read(fileName: String, maxAgeMs: Long): String? {
        val file = File(context.filesDir, fileName)
        if (!file.exists()) return null

        val age = System.currentTimeMillis() - file.lastModified()
        if (age > maxAgeMs) return null

        return try {
            file.readText()
        } catch (e: IOException) {
            Log.w(TAG, "Failed to read cache file: $fileName", e)
            null
        }
    }
}
