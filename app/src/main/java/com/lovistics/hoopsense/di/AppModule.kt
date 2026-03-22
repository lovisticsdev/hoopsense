package com.lovistics.hoopsense.di

import android.content.Context
import com.lovistics.hoopsense.data.cache.FileCache
import com.lovistics.hoopsense.data.repository.GameRepository
import com.lovistics.hoopsense.domain.repository.GameDataRepository
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(): OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .build()

    @Provides
    @Singleton
    fun provideFileCache(@ApplicationContext context: Context): FileCache {
        return FileCache(context)
    }

    @Provides
    @Singleton
    fun provideGameRepository(
        json: Json,
        fileCache: FileCache,
        client: OkHttpClient
    ): GameDataRepository {
        return GameRepository(json, fileCache, client)
    }
}
